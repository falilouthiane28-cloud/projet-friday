"""Passerelle d'outils : chaque appel de Claude passe par le GuardrailsEngine, puis est audité.

Le serveur MCP (`mcp_server.py`, lancé par Claude Code) relaie ici, par un socket Unix
dans un dossier privé (0700), les requêtes `{"op": "list"}` et
`{"op": "call", "name", "arguments"}`. Réponse : `{"ok", "text"}`.

Décision par tier :
- Tier 0 : refus, sans dérogation.
- Tier 1 : confirmation du maître (carte Autoriser/Refuser dans la bulle) ; sans réponse
  en `confirm_timeout` secondes, c'est un refus.
- Tier 2 : exécution puis notification dans la bulle.
- Tier 3-4 : exécution, journalisée.

Agents (phase 3, étape 3) : avec un registre, chaque appelant (`conductor` ou un agent) ne
voit et n'appelle que ses outils ; les appels faits pendant une délégation (`run`) sont
gardés pour le Validateur.

Phase 7 (durcissement) :
- Jetons de capacité : chaque relais MCP reçoit un jeton aléatoire lié à un appelant (et à
  une délégation) ; la passerelle ignore le champ `agent` de la requête et ne croit que le
  jeton. Requête sans jeton valide → refus. Le jeton d'une délégation est révoqué à sa fin.
- « CaMeL light » : un contexte (tour du Conductor, délégation) qui a lu du contenu non
  fiable (`guardrails/taint.py`) est contaminé ; ses mutations passent en confirmation.
  Une délégation hérite de la contamination du Conductor, et la lui rend à sa fin. La
  contamination du Conductor est remise à zéro à chaque nouvelle demande du maître.

Phase 8 (communication) : un outil `external` (envoi d'e-mail ou de message) est une sortie
externe (Tier 1 au moins). Si son contexte a lu une source à la fois privée et non fiable
(e-mails, messages), c'est la « lethal trifecta » : refus T0-TRIFECTA.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import secrets
import tempfile
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..audit import AuditLog
from ..guardrails import Action, Approval, GuardrailsEngine, reads_private, taint_of
from ..log import get_logger
from .builtin import Tool, ToolError

CONDUCTOR = "conductor"

Confirmer = Callable[[str, str], Awaitable[bool]]      # (résumé, action) → accord du maître
Notifier = Callable[[str], None]

MCP_SERVER_PATH = Path(__file__).with_name("mcp_server.py")
CONFIRM_TIMEOUT_S = 60.0


def _fingerprint(args: Any) -> str:
    return hashlib.sha256(json.dumps(args, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:16]


@dataclass(frozen=True)
class ToolRecord:
    """Un appel d'outil fait pendant une délégation (pour le Validateur)."""
    tool: str
    ok: bool
    text: str


class ToolGateway:
    def __init__(self, tools: Sequence[Tool], guardrails: GuardrailsEngine, audit: AuditLog | None = None,
                 confirm: Confirmer | None = None, notify: Notifier | None = None,
                 confirm_timeout: float = CONFIRM_TIMEOUT_S, allowed: Callable[[str], frozenset[str]] | None = None) -> None:
        self.tools = {t.name: t for t in tools}
        self.allowed = allowed                       # appelant → outils permis (None : tout, sans agents)
        self._runs: dict[str, list[ToolRecord]] = {}
        self._tokens: dict[str, tuple[str, str | None]] = {}   # jeton → (appelant, délégation)
        self._taint: dict[str, set[str]] = {}                   # contexte → sources non fiables lues
        self.guardrails = guardrails
        self.audit = audit
        self.confirm = confirm
        self.notify = notify
        self.confirm_timeout = confirm_timeout
        self.socket_path: Path | None = None
        self._server: asyncio.AbstractServer | None = None
        self._dir: str | None = None
        self._log = get_logger("friday.tools")

    # --- appels ----------------------------------------------------------------------------

    def add_tools(self, tools: Sequence[Tool]) -> None:
        for t in tools:
            self.tools[t.name] = t

    def _permitted(self, agent: str) -> set[str]:
        return set(self.tools) if self.allowed is None else set(self.allowed(agent)) & set(self.tools)

    def list_tools(self, agent: str = CONDUCTOR) -> list[dict[str, Any]]:
        permitted = self._permitted(agent)
        return [t.mcp() for t in self.tools.values() if t.name in permitted]

    def begin_run(self, run: str) -> None:
        self._runs[run] = []
        inherited = self._taint.get(CONDUCTOR)
        if inherited:                                # la consigne vient d'un Conductor contaminé
            self._taint[run] = set(inherited)

    def end_run(self, run: str) -> list[ToolRecord]:
        for tok, (_, r) in list(self._tokens.items()):
            if r == run:
                del self._tokens[tok]                # jeton de la délégation révoqué
        taint = self._taint.pop(run, None)
        if taint:                                    # le compte rendu de l'agent porte ce contenu
            self._taint.setdefault(CONDUCTOR, set()).update(taint)
        return self._runs.pop(run, [])

    # --- contamination (CaMeL light) ---------------------------------------------------------

    def new_turn(self) -> None:
        """Nouvelle demande du maître : le Conductor repart d'un contexte de confiance."""
        self._taint.pop(CONDUCTOR, None)

    def taint(self, agent: str = CONDUCTOR, run: str | None = None) -> frozenset[str]:
        return frozenset(self._taint.get(self._context(agent, run), ()))

    @staticmethod
    def _context(agent: str, run: str | None) -> str:
        return run if run is not None else agent

    async def call(self, name: Any, arguments: Any, agent: str = CONDUCTOR, run: str | None = None) -> tuple[bool, str]:
        ok, text = await self._call(name, arguments, agent, run)
        if run is not None and run in self._runs:
            self._runs[run].append(ToolRecord(str(name), ok, text[:300]))
        return ok, text

    async def _call(self, name: Any, arguments: Any, agent: str, run: str | None = None) -> tuple[bool, str]:
        tool = self.tools.get(name) if isinstance(name, str) else None
        if tool is None:
            self._record(str(name), None, None, arguments, "unknown_tool")
            return False, f"Outil inconnu : {name}."
        if tool.name not in self._permitted(agent):
            self._record(tool.name, tool.action, None, arguments, "forbidden_tool", agent=agent)
            return False, f"L'outil {tool.name} n'est pas autorisé pour {agent}. Ne réessaie pas."
        try:
            args = tool.validate(arguments)
            summary = tool.summary(args)
        except ToolError as exc:
            self._record(tool.name, tool.action, None, arguments, "invalid_args")
            return False, str(exc)

        code_field = tool.extra.get("code_field")
        ctx = self._context(agent, run)
        taint = tuple(sorted(self._taint.get(ctx, ())))
        verdict = self.guardrails.evaluate(Action(tool.action, params=args, actor=agent,
                                                  destination=tool.destination, taint_sources=taint,
                                                  external_communication=tool.external,
                                                  reads_private_data=reads_private(taint),
                                                  code=args.get(code_field) if code_field else None))
        tier = int(verdict.tier)
        if verdict.blocked:
            self._record(tool.name, tool.action, tier, args, "blocked", verdict.rule_id, taint=taint)
            return False, f"Action interdite par les règles de sécurité de Friday ({verdict.rule_id}). Ne réessaie pas."
        if verdict.requires_confirmation:
            if verdict.reasons:                      # contamination : montrer l'action brute, pas la paraphrase
                raw = json.dumps(args, ensure_ascii=False, sort_keys=True)
                summary = (f"{summary}\n⚠ {verdict.reasons[0]}.\nAction brute : {tool.name} {raw[:400]}")
            ok, why = await self._ask_master(summary, tool.action)
            if not ok:
                self._record(tool.name, tool.action, tier, args, "refused", taint=taint)
                reason = {"answered": "Le maître a refusé cette action", "timeout": "Le maître n'a pas répondu en "
                          f"{int(self.confirm_timeout)} s : action refusée par défaut"}.get(why, "Personne ne peut "
                          "confirmer cette action : refusée")
                return False, reason + ". Ne la refais pas sans nouvelle demande de sa part."
        try:
            text = await tool.run(args)
        except ToolError as exc:
            self._record(tool.name, tool.action, tier, args, "error")
            return False, str(exc)
        except Exception as exc:
            self._log.exception("tools.failed", tool=tool.name)
            self._record(tool.name, tool.action, tier, args, "error")
            return False, f"L'outil a échoué ({type(exc).__name__})."
        source = taint_of(tool.action)
        if source is not None:                       # du contenu non fiable entre dans ce contexte
            self._taint.setdefault(ctx, set()).add(source)
        self._record(tool.name, tool.action, tier, args, "executed", taint=taint)
        if verdict.approval is Approval.NOTIFY and self.notify is not None:
            self.notify(text.splitlines()[0] if text.strip() else summary)     # « Rappel … créé … »
        return True, text

    async def _ask_master(self, summary: str, action: str) -> tuple[bool, str]:
        if self.confirm is None:                     # personne pour confirmer : refus
            ok, why = False, "no_ui"
        else:
            try:
                ok = bool(await asyncio.wait_for(self.confirm(summary, action), self.confirm_timeout))
                why = "answered"
            except TimeoutError:
                ok, why = False, "timeout"
        if self.audit is not None:
            self.audit.append("tools", "tool.confirm", {"action": action, "ok": ok, "why": why})
        return ok, why

    def _record(self, tool: str, action: str | None, tier: int | None, args: Any, outcome: str,
                rule_id: str | None = None, agent: str | None = None, taint: Sequence[str] = ()) -> None:
        fields: dict[str, Any] = {"tool": tool, "action": action, "tier": tier, "outcome": outcome,
                                  "args_sha256": _fingerprint(args), "rule_id": rule_id}
        if agent is not None:
            fields["agent"] = agent
        if taint:
            fields["taint"] = list(taint)
        self._log.info("tools.call", **fields)
        if self.audit is not None:
            self.audit.append("tools", "tool.call", fields)

    # --- socket ----------------------------------------------------------------------------

    async def start(self, socket_path: Path | None = None) -> Path:
        if socket_path is None:
            self._dir = tempfile.mkdtemp(prefix="friday-")        # 0700 : seul l'utilisateur y accède
            socket_path = Path(self._dir) / "tools.sock"
        if socket_path.exists():
            socket_path.unlink()
        self._server = await asyncio.start_unix_server(self._client, path=str(socket_path))
        os.chmod(socket_path, 0o600)
        self.socket_path = socket_path
        return socket_path

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        if self.socket_path is not None and self.socket_path.exists():
            self.socket_path.unlink()
        if self._dir is not None:
            try:
                os.rmdir(self._dir)
            except OSError:
                pass

    async def _client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            line = await reader.readline()
            try:
                req = json.loads(line)
            except json.JSONDecodeError:
                req = {}
            op = req.get("op") if isinstance(req, dict) else None
            token = req.get("token") if isinstance(req, dict) else None
            who = self._tokens.get(token) if isinstance(token, str) else None
            if who is None:                          # le champ « agent » de la requête n'est jamais cru
                if op in ("list", "call"):
                    self._record(str(req.get("name")), None, None, {}, "bad_token")
                op = "denied"
            agent, run = who or (CONDUCTOR, None)
            if op == "denied":
                out: dict[str, Any] = {"ok": False, "text": "Jeton de capacité absent ou révoqué : requête refusée."}
            elif op == "list":
                out = {"tools": self.list_tools(agent)}
            elif op == "call":
                ok, text = await self.call(req.get("name"), req.get("arguments"), agent, run)
                out = {"ok": ok, "text": text}
            else:
                out = {"ok": False, "text": "requête invalide"}
            writer.write((json.dumps(out, ensure_ascii=False) + "\n").encode())
            await writer.drain()
        finally:
            writer.close()

    # --- configuration pour Claude Code --------------------------------------------------

    def mcp_config(self, python: str, agent: str = CONDUCTOR, run: str | None = None) -> str:
        """JSON pour `--mcp-config` : le relais stdio, lancé en mode isolé (-I), au nom d'un appelant."""
        assert self.socket_path is not None, "start() d'abord"
        token = secrets.token_urlsafe(24)            # capacité : cet appelant, cette délégation
        self._tokens[token] = (agent, run)
        args = ["-I", str(MCP_SERVER_PATH), "--socket", str(self.socket_path), "--token", token]
        if agent != CONDUCTOR:
            args += ["--agent", agent]
        if run is not None:
            args += ["--run", run]
        return json.dumps({"mcpServers": {"friday": {"type": "stdio", "command": python, "args": args}}})
