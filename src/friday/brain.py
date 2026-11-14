"""Cerveau de Friday : produit la réponse à un énoncé.

Phase 2 : `LocalBrain` (compétences locales instantanées : heure, date) et une
réponse d'attente pour le reste. Phase 3 : `ClaudeCodeBrain` (Claude Code).
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Protocol

from .conductor import Intent, RoutingDecision, normalize

_JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
_MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
         "septembre", "octobre", "novembre", "décembre")


class Brain(Protocol):
    async def respond(self, text: str, decision: RoutingDecision) -> str: ...


def dire_heure(now: datetime) -> str:
    h, m = now.hour, now.minute
    heures = {0: "minuit", 12: "midi", 1: "une heure"}.get(h, f"{h} heures")
    return f"Il est {heures}." if m == 0 else f"Il est {heures} {m:02d}."


def dire_date(now: datetime) -> str:
    jour = "1er" if now.day == 1 else str(now.day)
    return f"Nous sommes le {_JOURS[now.weekday()]} {jour} {_MOIS[now.month - 1]} {now.year}."


class LocalBrain:
    """Réponses locales sans LLM, pour les commandes simples et les tests de latence."""

    def __init__(self, clock: Callable[[], datetime] = datetime.now) -> None:
        self.clock = clock

    async def respond(self, text: str, decision: RoutingDecision) -> str:
        t = normalize(text)
        if "heure" in t or "what time" in t:
            return dire_heure(self.clock())
        if "date" in t or "quel jour" in t or "on est le" in t:
            return dire_date(self.clock())
        if decision.intent is Intent.CONVERSATION:
            return "Je vous écoute."
        return f"Bien reçu. L'agent {decision.agent} sera branché à la phase 3."
