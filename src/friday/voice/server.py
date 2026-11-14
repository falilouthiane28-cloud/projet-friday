"""Cœur Python en sous-processus de l'app Swift `friday-app` (`python -m friday --serve`).

Protocole JSON Lines (stdin → stdout ; journaux sur stderr) :
- app → cœur : ask{id, text, source}, metrics{ttfa_ms}, reset, confirm_result{id, ok}, shutdown,
  memory_list, memory_forget{id}
- cœur → app : ready{name, brain, tools?}, chunk{id, text} (une phrase, réponse en cours),
  reply{id, text, intent, agent, streamed?, login_required?}, error{message},
  confirm{id, summary, action} (action Tier 1 : Autoriser/Refuser), confirm_expired{id},
  notice{text} (action Tier 2 exécutée),
  memory{facts: [{id, text, category, created_at}], available, forgot?} (réponse à memory_list / memory_forget)

Outils : si une `ToolGateway` est fournie, son socket est ouvert au démarrage et Claude Code
reçoit le serveur MCP relais ; les confirmations Tier 1 passent par l'app.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import sys
from collections.abc import Callable
from typing import IO, Any

from ..audit import AuditLog
from ..brain import Brain
from ..claude_brain import LOGIN_HELP, SentenceSplitter
from ..conductor import Conductor
from ..log import get_logger
from ..tools import ToolGateway

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
    if kind == "confirm_result":
        if not isinstance(msg.get("id"), int) or not isinstance(msg.get("ok"), bool):
            return None
        return msg
    if kind == "memory_forget":
        if not isinstance(msg.get("id"), int) or isinstance(msg.get("id"), bool):
            return None
        return msg
    if kind in ("metrics", "reset", "shutdown", "memory_list"):
        return msg
    return None


class CoreServer:
    def __init__(self, conductor: Conductor, brain: Brain, audit: AuditLog | None = None, name: str = "Friday",
                 gateway: ToolGateway | None = None) -> None:
        self.conductor = conductor
        self.brain = brain
        self.audit = audit
        self.name = name
        self.gateway = gateway
        self._turns = 0
        self._emit: Callable[[dict[str, Any]], None] | None = None
        self._confirms: dict[int, asyncio.Future[bool]] = {}
        self._confirm_ids = itertools.count(1)
        self._log = get_logger("friday.serve")
        if gateway is not None:
            gateway.confirm = self._confirm
            gateway.notify = self._notify

    async def _confirm(self, summary: str, action: str) -> bool:
        """Demande Autoriser/Refuser à l'app ; le délai (refus par défaut) est géré par la passerelle."""
        if self._emit is None:
            return False
        cid = next(self._confirm_ids)
        fut: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
        self._confirms[cid] = fut
        self._emit({"type": "confirm", "id": cid, "summary": summary, "action": action})
        try:
            return await fut
        except asyncio.CancelledError:              # délai dépassé : la carte se ferme dans l'app
            self._emit({"type": "confirm_expired", "id": cid})
            raise
        finally:
            self._confirms.pop(cid, None)

    def _notify(self, text: str) -> None:
        if self._emit is not None:
            self._emit({"type": "notice", "text": text})

    def _deny_pending(self) -> None:
        for fut in self._confirms.values():
            if not fut.done():
                fut.set_result(False)

    async def handle(self, msg: dict[str, Any]) -> dict[str, Any] | None:
        """Traite un message de l'app ; retourne la réponse à émettre (ou None)."""
        kind = msg["type"]
        if kind == "ask":
            text = msg["text"].strip()
            source = msg.get("source", "text")
            if self.gateway is not None and not self._turns:
                self.gateway.new_turn()              # CaMeL light : nouvelle demande, contexte de confiance
            decision = self.conductor.handle(text, source=source)
            self._turns += 1                         # un tour encore en cours garde sa contamination
            try:
                reply = await self.brain.respond(text, decision, source)
            finally:
                self._turns -= 1
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
        elif kind == "confirm_result":
            fut = self._confirms.get(msg["id"])
            if fut is not None and not fut.done():
                fut.set_result(msg["ok"])
        elif kind == "reset":
            self._deny_pending()
            if hasattr(self.brain, "reset"):
                self.brain.reset()
        elif kind == "memory_list":
            return self._memory_message()
        elif kind == "memory_forget":
            memory = getattr(self.brain, "memory", None)
            forgot = bool(memory is not None and memory.forget_id(msg["id"]))
            if forgot and hasattr(self.brain, "reset"):   # la conversation de Claude contient encore le fait
                self.brain.reset()
            return self._memory_message(forgot=forgot)
        return None

    def _memory_message(self, **extra: Any) -> dict[str, Any]:
        """Faits mémorisés pour « Ce dont Friday se souvient… » (les plus récents d'abord)."""
        memory = getattr(self.brain, "memory", None)
        facts = [] if memory is None else [
            {"id": f.id, "text": f.text, "category": f.category, "created_at": f.created_at}
            for f in reversed(memory.all())]
        return {"type": "memory", "facts": facts, "available": memory is not None, **extra}

    async def run(self, stdin: IO[str] | None = None, stdout: IO[str] | None = None) -> int:
        stdin = stdin or sys.stdin
        stdout = stdout or sys.stdout
        loop = asyncio.get_running_loop()

        def emit(obj: dict[str, Any]) -> None:
            stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
            stdout.flush()

        self._emit = emit
        ready = {"type": "ready", "name": self.name, "brain": getattr(self.brain, "name", "local")}
        if self.gateway is not None and hasattr(self.brain, "use_tools"):
            try:
                await self.gateway.start()
                self.brain.use_tools(self.gateway.mcp_config(sys.executable))
                ready["tools"] = [t["name"] for t in self.gateway.list_tools()]
            except OSError:
                self._log.exception("serve.tools_failed")
        if binary := getattr(getattr(self.brain, "remote", None), "binary", None):
            ready["claude_binary"] = str(binary)     # pour « Connecter Claude Code… » dans l'app
        emit(ready)
        pending: set[asyncio.Task[None]] = set()
        if hasattr(self.brain, "prewarm"):           # Claude Code démarre pendant que l'app s'ouvre
            warm = asyncio.create_task(self._prewarm())
            pending.add(warm)
            warm.add_done_callback(pending.discard)
        while True:
            line = await loop.run_in_executor(None, stdin.readline)
            if not line:                       # stdin fermé : l'app s'est arrêtée
                self._deny_pending()
                await asyncio.gather(*pending)
                await self._close()
                return 0
            if not line.strip():
                continue
            msg = parse_app_message(line)
            if msg is None:
                self._log.warning("serve.invalid_message", raw=line[:200])
                emit({"type": "error", "message": "message invalide"})
                continue
            if msg["type"] == "shutdown":
                self._deny_pending()               # personne ne répondra : refus
                await asyncio.gather(*pending)     # les réponses en cours partent avant l'arrêt
                await self._close()
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

    async def _prewarm(self) -> None:
        try:
            await self.brain.prewarm()
        except Exception:
            self._log.exception("serve.prewarm_failed")

    async def _close(self) -> None:
        if hasattr(self.brain, "close"):
            await self.brain.close()
        if self.gateway is not None:
            await self.gateway.close()

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
