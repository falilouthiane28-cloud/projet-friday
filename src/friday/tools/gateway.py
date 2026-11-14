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
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import tempfile
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Any

from ..audit import AuditLog
from ..guardrails import Action, Approval, GuardrailsEngine
from ..log import get_logger
from .builtin import Tool, ToolError

Confirmer = Callable[[str, str], Awaitable[bool]]      # (résumé, action) → accord du maître
Notifier = Callable[[str], None]

MCP_SERVER_PATH = Path(__file__).with_name("mcp_server.py")
CONFIRM_TIMEOUT_S = 60.0


def _fingerprint(args: Any) -> str:
    return hashlib.sha256(json.dumps(args, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:16]


class ToolGateway:
    def __init__(self, tools: Sequence[Tool], guardrails: GuardrailsEngine, audit: AuditLog | None = None,
                 confirm: Confirmer | None = None, notify: Notifier | None = None,
                 confirm_timeout: float = CONFIRM_TIMEOUT_S) -> None:
        self.tools = {t.name: t for t in tools}
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

    def list_tools(self) -> list[dict[str, Any]]:
        return [t.mcp() for t in self.tools.values()]

    async def call(self, name: Any, arguments: Any) -> tuple[bool, str]:
        tool = self.tools.get(name) if isinstance(name, str) else None
        if tool is None:
            self._record(str(name), None, None, arguments, "unknown_tool")
            return False, f"Outil inconnu : {name}."
        try:
            args = tool.validate(arguments)
            summary = tool.summary(args)
        except ToolError as exc:
            self._record(tool.name, tool.action, None, arguments, "invalid_args")
            return False, str(exc)

        verdict = self.guardrails.evaluate(Action(tool.action, params=args, actor="claude",
                                                  destination=tool.destination))
        tier = int(verdict.tier)
        if verdict.blocked:
            self._record(tool.name, tool.action, tier, args, "blocked", verdict.rule_id)
            return False, f"Action interdite par les règles de sécurité de Friday ({verdict.rule_id}). Ne réessaie pas."
        if verdict.requires_confirmation:
            ok, why = await self._ask_master(summary, tool.action)
            if not ok:
                self._record(tool.name, tool.action, tier, args, "refused")
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
        self._record(tool.name, tool.action, tier, args, "executed")
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
                rule_id: str | None = None) -> None:
        fields = {"tool": tool, "action": action, "tier": tier, "outcome": outcome,
                  "args_sha256": _fingerprint(args), "rule_id": rule_id}
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
            if op == "list":
                out: dict[str, Any] = {"tools": self.list_tools()}
            elif op == "call":
                ok, text = await self.call(req.get("name"), req.get("arguments"))
                out = {"ok": ok, "text": text}
            else:
                out = {"ok": False, "text": "requête invalide"}
            writer.write((json.dumps(out, ensure_ascii=False) + "\n").encode())
            await writer.drain()
        finally:
            writer.close()

    # --- configuration pour Claude Code --------------------------------------------------

    def mcp_config(self, python: str) -> str:
        """JSON pour `--mcp-config` : le relais stdio, lancé en mode isolé (-I)."""
        assert self.socket_path is not None, "start() d'abord"
        return json.dumps({"mcpServers": {"friday": {
            "type": "stdio", "command": python, "args": ["-I", str(MCP_SERVER_PATH), "--socket", str(self.socket_path)],
        }}})
