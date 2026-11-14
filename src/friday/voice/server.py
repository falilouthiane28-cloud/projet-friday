"""Cœur Python en sous-processus de l'app Swift `friday-app` (`python -m friday --serve`).

Protocole JSON Lines (stdin → stdout ; journaux sur stderr) :
- app → cœur : ask{id, text, source}, metrics{ttfa_ms}, shutdown
- cœur → app : ready{name}, reply{id, text, intent, agent}, error{message}
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import IO, Any

from ..audit import AuditLog
from ..brain import Brain
from ..conductor import Conductor
from ..log import get_logger

SOURCES = frozenset({"voice", "text"})


def parse_app_message(line: str | bytes) -> dict[str, Any] | None:
    try:
        msg = json.loads(line)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(msg, dict):
        return None
    kind = msg.get("type")
    if kind == "ask":
        if not isinstance(msg.get("text"), str) or not isinstance(msg.get("id"), int):
            return None
        if msg.get("source", "text") not in SOURCES:
            return None
        return msg
    if kind in ("metrics", "shutdown"):
        return msg
    return None


class CoreServer:
    def __init__(self, conductor: Conductor, brain: Brain, audit: AuditLog | None = None, name: str = "Friday") -> None:
        self.conductor = conductor
        self.brain = brain
        self.audit = audit
        self.name = name
        self._log = get_logger("friday.serve")

    async def handle(self, msg: dict[str, Any]) -> dict[str, Any] | None:
        """Traite un message de l'app ; retourne la réponse à émettre (ou None)."""
        kind = msg["type"]
        if kind == "ask":
            text = msg["text"].strip()
            source = msg.get("source", "text")
            decision = self.conductor.handle(text, source=source)
            reply = await self.brain.respond(text, decision)
            return {"type": "reply", "id": msg["id"], "text": reply,
                    "intent": decision.intent.value, "agent": decision.agent}
        if kind == "metrics":
            ttfa = int(msg.get("ttfa_ms", 0))
            self._log.info("voice.ttfa", ttfa_ms=ttfa)
            if self.audit is not None:
                self.audit.append("voice", "voice.ttfa", {"ttfa_ms": ttfa})
        return None

    async def run(self, stdin: IO[str] | None = None, stdout: IO[str] | None = None) -> int:
        stdin = stdin or sys.stdin
        stdout = stdout or sys.stdout
        loop = asyncio.get_running_loop()

        def emit(obj: dict[str, Any]) -> None:
            stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
            stdout.flush()

        emit({"type": "ready", "name": self.name})
        while True:
            line = await loop.run_in_executor(None, stdin.readline)
            if not line:                       # stdin fermé : l'app s'est arrêtée
                return 0
            if not line.strip():
                continue
            msg = parse_app_message(line)
            if msg is None:
                self._log.warning("serve.invalid_message", raw=line[:200])
                emit({"type": "error", "message": "message invalide"})
                continue
            if msg["type"] == "shutdown":
                return 0
            try:
                out = await self.handle(msg)
            except Exception as exc:          # une erreur du cerveau ne doit pas tuer le cœur
                self._log.exception("serve.handle_failed")
                emit({"type": "error", "message": str(exc)})
                continue
            if out is not None:
                emit(out)
