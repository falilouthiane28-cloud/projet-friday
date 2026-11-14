"""Extraction de faits depuis un énoncé de l'utilisateur.

`FactExtractor` est l'interface ; `RuleBasedExtractor` est la version simple à
règles (tests, hors ligne). La version Claude viendra au branchement.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ExtractedFact:
    text: str
    category: str = "general"
    key: str | None = None        # même clé = le nouveau fait remplace l'ancien
    confidence: float = 0.8


class FactExtractor(Protocol):
    def extract(self, utterance: str) -> list[ExtractedFact]: ...


def slug(text: str) -> str:
    """Clé stable : minuscules, sans accents, mots séparés par « _ »."""
    norm = unicodedata.normalize("NFKD", text.lower())
    norm = "".join(c for c in norm if not unicodedata.combining(c))
    return "_".join(re.findall(r"[a-z0-9]+", norm))


_END = r"\s*(?:[.!?,;]|$)"
_VALUE = r"(?P<value>[^.!?,;]+?)"
_APOS = r"['’]"

_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(rf"\bje m{_APOS}appelle\s+{_VALUE}{_END}", re.I), "nom"),
    (re.compile(rf"\bmon (?:pr[ée]nom|nom) est\s+{_VALUE}{_END}", re.I), "nom"),
    (re.compile(
        rf"\b(?:mon|ma|mes)\s+(?P<thing>[\w’' -]+?)\s+(?P<adj>pr[ée]f[ée]r[ée]e?s?)\s+"
        rf"(?:est|sont|c{_APOS}est|ce sont)\s+(?:le |la |les |l{_APOS}|du |de la |des )?{_VALUE}{_END}",
        re.I), "prefere_chose"),
    (re.compile(rf"\bj{_APOS}habite\s+(?:à|a|au|en)\s+{_VALUE}{_END}", re.I), "ville"),
    (re.compile(rf"\bje pr[ée]f[èe]re\s+{_VALUE}{_END}", re.I), "prefere"),
    (re.compile(rf"\bj{_APOS}(?:aime|adore)\s+{_VALUE}{_END}", re.I), "aime"),
    (re.compile(rf"\bje n{_APOS}aime pas\s+{_VALUE}{_END}", re.I), "aime_pas"),
]


class RuleBasedExtractor:
    """Quelques tournures françaises courantes ; tout le reste est ignoré."""

    def extract(self, utterance: str) -> list[ExtractedFact]:
        facts: list[ExtractedFact] = []
        for pattern, kind in _RULES:
            for m in pattern.finditer(utterance):
                value = m.group("value").strip()
                if not value:
                    continue
                fact = self._build(kind, value, m.groupdict().get("thing"), m.groupdict().get("adj"))
                if fact and all(f.text != fact.text for f in facts):
                    facts.append(fact)
        return facts

    @staticmethod
    def _build(kind: str, value: str, thing: str | None, adj: str | None = None) -> ExtractedFact | None:
        if kind == "nom":
            return ExtractedFact(f"L'utilisateur s'appelle {value}", "identite", "identite.nom", 0.9)
        if kind == "ville":
            return ExtractedFact(f"L'utilisateur habite à {value}", "identite", "identite.ville", 0.8)
        if kind == "prefere_chose" and thing:
            thing = thing.strip()
            return ExtractedFact(f"{thing[:1].upper()}{thing[1:]} {(adj or 'préféré').lower()} : {value}",
                                 "preference", f"preference.{slug(thing)}", 0.9)
        if kind == "prefere":
            return ExtractedFact(f"L'utilisateur préfère {value}", "preference", None, 0.8)
        if kind == "aime":
            return ExtractedFact(f"L'utilisateur aime {value}", "preference", None, 0.7)
        if kind == "aime_pas":
            return ExtractedFact(f"L'utilisateur n'aime pas {value}", "preference", None, 0.7)
        return None
