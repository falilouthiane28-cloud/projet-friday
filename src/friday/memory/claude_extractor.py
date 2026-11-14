"""Extraction des faits durables par Claude (appel séparé, modèle rapide).

Après chaque échange, un `claude -p` one-shot (haiku, sans outils, sans session
reprise ni conservée, dossier de travail à part) lit l'énoncé de l'utilisateur et la réponse
de Friday et renvoie les faits durables en JSON. La conversation principale
(processus persistant) n'est jamais touchée.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ..claude_brain import ClaudeError, Runner, clean_env, parse_result, run_process
from ..log import get_logger
from .extractor import ExtractedFact, slug

CATEGORIES = frozenset({"identite", "proches", "preference", "habitude", "projet", "travail", "sante", "general"})

SYSTEM_PROMPT = """Tu extrais la mémoire à long terme d'un assistant personnel.
On te donne un échange (utilisateur puis assistant) et les faits déjà connus.
Retourne UNIQUEMENT du JSON : {"facts": [{"text": "...", "category": "...", "key": "...", "confidence": 0.9}]}

Règles :
- Seulement des faits DURABLES sur l'utilisateur, affirmés par l'utilisateur lui-même : identité, ville, proches
  (prénoms, liens), préférences, habitudes, projets en cours, travail, santé si l'utilisateur la mentionne.
- Rien sur l'assistant, rien de passager (humeur du moment, question posée, météo, heure), aucune supposition.
- text : une phrase courte en français à la 3e personne, qui commence par « L'utilisateur » (ex. « La sœur de
  l'utilisateur s'appelle Awa », « L'utilisateur boit son café sans sucre »).
- category parmi : identite, proches, preference, habitude, projet, travail, sante, general.
- key : identifiant stable en snake_case pour un fait qui n'a qu'une valeur à la fois (ex. proches.soeur.prenom,
  identite.ville, preference.cafe) ; réutilise la clé d'un fait connu quand le nouveau le remplace ; null sinon.
- confidence : 0.9 si affirmé clairement, 0.6 si implicite.
- JAMAIS de secret : mot de passe, code (PIN, porte, carte, 2FA), numéro de carte ou de compte, IBAN, clé, jeton.
- Ne répète pas un fait déjà connu à l'identique. Aucun fait : {"facts": []}."""

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def parse_facts(raw: str) -> list[ExtractedFact]:
    """Texte renvoyé par Claude → faits valides (le reste est ignoré)."""
    m = _JSON_BLOCK.search(raw)
    if not m:
        raise ValueError("pas de JSON")
    data = json.loads(m.group())
    items = data.get("facts") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ValueError("champ facts absent")
    facts: list[ExtractedFact] = []
    for item in items[:10]:
        if not isinstance(item, dict) or not isinstance(item.get("text"), str):
            continue
        text = " ".join(item["text"].split())[:300]
        if len(text) < 4:
            continue
        category = item.get("category") if item.get("category") in CATEGORIES else "general"
        key = item.get("key")
        key = (".".join(slug(p) for p in key.split(".") if slug(p)) or None) if isinstance(key, str) else None
        try:
            confidence = float(item.get("confidence", 0.8))
        except (TypeError, ValueError):
            confidence = 0.8
        facts.append(ExtractedFact(text, category, key, max(0.1, min(1.0, confidence))))
    return facts


class ClaudeFactExtractor:
    """Extracteur asynchrone (`aextract`) ; `extract` (synchrone) n'est pas fourni."""

    def __init__(self, binary: Path, workdir: Path, model: str = "haiku", timeout: float = 45,
                 runner: Runner = run_process, env: Mapping[str, str] | None = None) -> None:
        self.binary = binary
        self.workdir = workdir                 # à part : ses sessions ne se mêlent pas à celles de Friday
        self.model = model
        self.timeout = timeout
        self.runner = runner
        self.env = clean_env(env if env is not None else os.environ)
        self._log = get_logger("friday.memory.extract")

    def command(self, prompt: str) -> list[str]:
        return [str(self.binary), "-p", prompt, "--output-format", "json", "--model", self.model,
                "--tools", "", "--strict-mcp-config", "--setting-sources", "", "--no-session-persistence",
                "--system-prompt", SYSTEM_PROMPT]

    @staticmethod
    def prompt(utterance: str, reply: str, known: Sequence[Any]) -> str:
        lines = ["Faits déjà connus :"]
        lines += [f"- [{f.key or '-'}] {f.text}" for f in list(known)[-40:]] or ["(aucun)"]
        lines += ["", "Échange :", f"Utilisateur : {utterance}", f"Assistant : {reply[:800]}"]
        return "\n".join(lines)

    async def aextract(self, utterance: str, reply: str = "", known: Sequence[Any] = ()) -> list[ExtractedFact]:
        self.workdir.mkdir(parents=True, exist_ok=True)
        code, out = await self.runner(self.command(self.prompt(utterance, reply, known)),
                                      self.env, self.workdir, self.timeout)
        text, _ = parse_result(code, out)
        try:
            return parse_facts(text)
        except (ValueError, json.JSONDecodeError) as exc:
            raise ClaudeError(f"extraction illisible : {exc}") from None
