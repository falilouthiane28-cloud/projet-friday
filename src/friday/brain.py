"""Cerveau de Friday : produit la réponse à un énoncé.

Phase 2 : `LocalBrain` (compétences locales instantanées : heure, date) et une
réponse d'attente pour le reste. Phase 3 : `ClaudeCodeBrain` (Claude Code).
"""

from __future__ import annotations

from datetime import datetime
from collections.abc import AsyncIterator
import re
from typing import Any, Callable, Protocol

from .conductor import Intent, RoutingDecision, normalize

_JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
_MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
         "septembre", "octobre", "novembre", "décembre")


class Brain(Protocol):
    async def respond(self, text: str, decision: RoutingDecision, source: str = "text") -> str: ...


def dire_heure(now: datetime) -> str:
    h, m = now.hour, now.minute
    heures = {0: "minuit", 12: "midi", 1: "une heure"}.get(h, f"{h} heures")
    return f"Il est {heures}." if m == 0 else f"Il est {heures} {m:02d}."


def dire_date(now: datetime) -> str:
    jour = "1er" if now.day == 1 else str(now.day)
    return f"Nous sommes le {_JOURS[now.weekday()]} {jour} {_MOIS[now.month - 1]} {now.year}."


class LocalBrain:
    """Réponses locales sans LLM, pour les commandes simples et les tests de latence."""

    name = "local"

    def __init__(self, clock: Callable[[], datetime] = datetime.now) -> None:
        self.clock = clock

    def quick(self, text: str) -> str | None:
        """Réponse instantanée si la demande est locale (heure, date), sinon None."""
        t = normalize(text)
        if "heure" in t or "what time" in t:
            return dire_heure(self.clock())
        if "date" in t or "quel jour" in t or "on est le" in t:
            return dire_date(self.clock())
        return None

    async def respond(self, text: str, decision: RoutingDecision, source: str = "text") -> str:
        if (reply := self.quick(text)) is not None:
            return reply
        if decision.intent is Intent.CONVERSATION:
            return "Je vous écoute."
        return f"Bien reçu. L'agent {decision.agent} sera branché à la phase 3."


# « oublie que je bois du café », « efface mon café préféré »…
_FORGET = re.compile(r"^(?:friday[ ,]*)?(?:oublie|efface)\s+(?:que\s+|ce que\s+)?(.+)$", re.IGNORECASE)


class HybridBrain:
    """Heure et date en local (instantané), tout le reste à Claude Code."""

    name = "Claude Code"

    def __init__(self, local: LocalBrain, remote: Brain, memory: Any = None) -> None:
        self.local = local
        self.remote = remote
        self.memory = memory                         # MemoryStore (phase 4), facultatif

    def _remember(self, text: str) -> tuple[str | None, str]:
        """Mémoire : « oublie … » → réponse locale ; sinon apprend l'énoncé et ajoute les faits utiles à la question."""
        if self.memory is None:
            return None, text
        if m := _FORGET.match(text.strip()):
            n = self.memory.forget(m.group(1).strip(" .!?"))
            if n:                                    # la conversation de Claude contient encore le fait : on l'efface aussi
                self.reset()
            return ("C'est oublié." if n else "Je n'avais rien retenu à ce sujet."), text
        self.memory.learn(text)
        ctx = self.memory.context_for(text)
        return None, (f"{ctx}\n\n{text}" if ctx else text)

    def reset(self) -> None:
        if hasattr(self.remote, "reset"):
            self.remote.reset()

    def use_tools(self, mcp_config: str | None) -> None:
        if hasattr(self.remote, "use_tools"):
            self.remote.use_tools(mcp_config)

    async def prewarm(self) -> None:
        if hasattr(self.remote, "prewarm"):
            await self.remote.prewarm()

    async def close(self) -> None:
        if hasattr(self.remote, "close"):
            await self.remote.close()

    async def respond(self, text: str, decision: RoutingDecision, source: str = "text") -> str:
        if (reply := self.local.quick(text)) is not None:
            return reply
        forgot, prompt = self._remember(text)
        if forgot is not None:
            return forgot
        from .claude_brain import ClaudeError
        try:
            return await self.remote.respond(prompt, decision, source)
        except ClaudeError as exc:
            return str(exc)

    async def stream(self, text: str, decision: RoutingDecision, source: str = "text") -> AsyncIterator[str]:
        """Comme respond, mais au fil de l'eau quand le cerveau distant le permet."""
        if (reply := self.local.quick(text)) is not None:
            yield reply
            return
        forgot, prompt = self._remember(text)
        if forgot is not None:
            yield forgot
            return
        from .claude_brain import ClaudeError
        streamer = getattr(self.remote, "stream", None)
        try:
            if streamer is None:
                yield await self.remote.respond(prompt, decision, source)
                return
            async for delta in streamer(prompt, decision, source):
                yield delta
        except ClaudeError as exc:
            yield str(exc)
