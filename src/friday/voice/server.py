"""Cœur Python en sous-processus de l'app Swift `friday-app` (`python -m friday --serve`).

Protocole JSON Lines (stdin → stdout ; journaux sur stderr) :
- app → cœur : ask{id, text, source}, metrics{ttfa_ms}, reset, shutdown
- cœur → app : ready{name, brain}, chunk{id, text} (une phrase, réponse en cours),
  reply{id, text, intent, agent, streamed?, login_required?}, error{message}
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Callable
from typing import IO, Any

from ..audit import AuditLog
from ..brain import Brain
from ..claude_brain import LOGIN_HELP, SentenceSplitter
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
    if kind in ("metrics", "reset", "shutdown"):
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
            reply = await self.brain.respond(text, decision, source)
            out = {"type": "reply", "id": msg["id"], "text": reply,
                   "intent": decision.intent.value, "agent": decision.agent}
            if reply == LOGIN_HELP:
                out["login_required"] = True
            return out
        if kind == "metrics":
            ttfa = int(msg.get("ttfa_ms", 0))
            self._log.info("voice.ttfa", ttfa_ms=ttfa)
            if self.audit is not None:
                self.audit.append("voice", "voice.ttfa", {"ttfa_ms": ttfa})
        elif kind == "reset" and hasattr(self.brain, "reset"):
            self.brain.reset()
        return None

    async def run(self, stdin: IO[str] | None = None, stdout: IO[str] | None = None) -> int:
        stdin = stdin or sys.stdin
        stdout = stdout or sys.stdout
        loop = asyncio.get_running_loop()

        def emit(obj: dict[str, Any]) -> None:
            stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
            stdout.flush()

        ready = {"type": "ready", "name": self.name, "brain": getattr(self.brain, "name", "local")}
        if binary := getattr(getattr(self.brain, "remote", None), "binary", None):
            ready["claude_binary"] = str(binary)     # pour « Connecter Claude Code… » dans l'app
        emit(ready)
        pending: set[asyncio.Task[None]] = set()
        while True:
            line = await loop.run_in_executor(None, stdin.readline)
            if not line:                       # stdin fermé : l'app s'est arrêtée
                await asyncio.gather(*pending)
                return 0
            if not line.strip():
                continue
            msg = parse_app_message(line)
            if msg is None:
                self._log.warning("serve.invalid_message", raw=line[:200])
                emit({"type": "error", "message": "message invalide"})
                continue
            if msg["type"] == "shutdown":
                await asyncio.gather(*pending)     # les réponses en cours partent avant l'arrêt
                return 0
            if msg["type"] == "ask":              # Claude peut prendre plusieurs secondes : en parallèle
                task = asyncio.create_task(self._answer(msg, emit))
                pending.add(task)
                task.add_done_callback(pending.discard)
                continue
            try:
                out = await self.handle(msg)
            except Exception as exc:          # une erreur du cerveau ne doit pas tuer le cœur
                self._log.exception("serve.handle_failed")
                emit({"type": "error", "message": str(exc)})
                continue
            if out is not None:
                emit(out)

    async def _answer(self, msg: dict[str, Any], emit: Callable[[dict[str, Any]], None]) -> None:
        streamer = getattr(self.brain, "stream", None)
        try:
            if streamer is not None:
                out = await self._stream_answer(msg, streamer, emit)
            else:
                out = await self.handle(msg)
        except Exception as exc:              # une erreur du cerveau ne doit pas tuer le cœur
            self._log.exception("serve.handle_failed")
            emit({"type": "error", "message": str(exc), "id": msg.get("id")})
            return
        if out is not None:
            emit(out)

    async def _stream_answer(self, msg: dict[str, Any], streamer: Any, emit: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
        """Émet chaque phrase dès qu'elle est complète (chunk), puis la réponse entière (reply)."""
        text = msg["text"].strip()
        source = msg.get("source", "text")
        decision = self.conductor.handle(text, source=source)
        splitter = SentenceSplitter()
        full = ""
        async for delta in streamer(text, decision, source):
            full += delta
            for sentence in splitter.feed(delta):
                emit({"type": "chunk", "id": msg["id"], "text": sentence})
        for sentence in splitter.flush():
            emit({"type": "chunk", "id": msg["id"], "text": sentence})
        out = {"type": "reply", "id": msg["id"], "text": full.strip(), "intent": decision.intent.value,
               "agent": decision.agent, "streamed": True}
        if full.strip() == LOGIN_HELP:
            out["login_required"] = True
        return out
