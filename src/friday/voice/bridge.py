"""Pont asyncio entre le cœur Python et le binaire Swift `friday-voice`.

Protocole JSON Lines :
- voix → cœur : ready, state, utterance{text}, barge_in, metrics{ttfa_ms}, error{message}
- cœur → voix : say{text}, stop, shutdown
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from typing import Any

from ..audit import AuditLog
from ..brain import Brain
from ..conductor import Conductor
from ..log import get_logger

VOICE_TYPES = frozenset({"ready", "state", "utterance", "barge_in", "metrics", "error"})


def parse_voice_message(line: str | bytes) -> dict[str, Any] | None:
    try:
        msg = json.loads(line)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(msg, dict) or msg.get("type") not in VOICE_TYPES:
        return None
    if msg["type"] == "utterance" and not isinstance(msg.get("text"), str):
        return None
    return msg


class VoiceBridge:
    def __init__(
        self,
        command: Sequence[str],
        conductor: Conductor,
        brain: Brain,
        audit: AuditLog | None = None,
    ) -> None:
        self.command = list(command)
        self.conductor = conductor
        self.brain = brain
        self.audit = audit
        self.state = "idle"
        self.ttfa_ms: list[int] = []
        self._proc: asyncio.subprocess.Process | None = None
        self._log = get_logger("friday.voice")

    async def send(self, msg: dict[str, Any]) -> None:
        assert self._proc and self._proc.stdin
        self._proc.stdin.write((json.dumps(msg, ensure_ascii=False) + "\n").encode())
        await self._proc.stdin.drain()

    async def run(self) -> int:
        """Lance le binaire et traite ses messages jusqu'à sa fin. Retourne son code de sortie."""
        self._proc = await asyncio.create_subprocess_exec(
            *self.command, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        )
        assert self._proc.stdout
        async for raw in self._proc.stdout:
            msg = parse_voice_message(raw)
            if msg is None:
                self._log.warning("voice.invalid_message", raw=raw[:200].decode(errors="replace"))
                continue
            await self._dispatch(msg)
        return await self._proc.wait()

    async def shutdown(self) -> None:
        if self._proc and self._proc.returncode is None:
            try:
                await self.send({"type": "shutdown"})
            except (BrokenPipeError, ConnectionResetError):
                pass
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=2)
            except TimeoutError:
                self._proc.kill()

    async def _dispatch(self, msg: dict[str, Any]) -> None:
        kind = msg["type"]
        if kind == "state":
            self.state = str(msg.get("state"))
            self._log.info("voice.state", state=self.state)
        elif kind == "utterance":
            decision = self.conductor.handle(msg["text"], source="voice")
            reply = await self.brain.respond(msg["text"], decision, "voice")
            await self.send({"type": "say", "text": reply})
        elif kind == "metrics":
            ttfa = int(msg.get("ttfa_ms", 0))
            self.ttfa_ms.append(ttfa)
            self._log.info("voice.ttfa", ttfa_ms=ttfa)
            if self.audit is not None:
                self.audit.append("voice", "voice.ttfa", {"ttfa_ms": ttfa})
        elif kind == "barge_in":
            self._log.info("voice.barge_in")
        elif kind == "error":
            self._log.error("voice.error", message=msg.get("message"))
        elif kind == "ready":
            self._log.info("voice.ready")
