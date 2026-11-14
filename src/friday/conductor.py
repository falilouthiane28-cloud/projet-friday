"""Conductor de base : classification d'intention d'un message texte.

Phase 1 : classifieur par mots-clés pondérés (FR + EN), sans LLM. L'interface
`IntentClassifier` permettra de brancher semantic-router puis Haiku en phase 3.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from .audit import AuditLog
from .guardrails import Action, GuardrailsEngine, Verdict
from .log import get_logger


class Intent(str, Enum):
    CONVERSATION = "conversation"
    RESEARCH = "research"
    CODE = "code"
    SCHEDULE = "schedule"
    HOME = "home"
    SYSTEM = "system"
    COMMUNICATION = "communication"


AGENT_BY_INTENT: dict[Intent, str] = {
    Intent.CONVERSATION: "conductor",
    Intent.RESEARCH: "researcher",
    Intent.CODE: "coder",
    Intent.SCHEDULE: "scheduler",
    Intent.HOME: "home_controller",
    Intent.SYSTEM: "system_monitor",
    Intent.COMMUNICATION: "communicator",
}


@dataclass(frozen=True)
class Classification:
    intent: Intent
    confidence: float
    matched: tuple[str, ...] = ()


@dataclass(frozen=True)
class RoutingDecision:
    intent: Intent
    agent: str
    confidence: float
    matched: tuple[str, ...]


class IntentClassifier(Protocol):
    def classify(self, text: str) -> Classification: ...


# Motifs appliqués sur le texte normalisé (minuscules, sans accents).
# Poids : 3 = très spécifique, 2 = spécifique, 1 = indice faible.
_RULES: dict[Intent, tuple[tuple[str, int], ...]] = {
    Intent.HOME: (
        (r"\b(allume|allumer|eteins|eteindre|eteint)\b", 3),
        (r"\b(lumieres?|lampes?|ampoules?|eclairage)\b", 3),
        (r"\b(thermostat|chauffage|climatisation|clim|volets?|stores?|serrure|prise connectee)\b", 3),
        (r"\b(turn (on|off)|lights?|home assistant)\b", 3),
        (r"\b(salon|chambre|cuisine|garage|jardin|entree)\b", 1),
        (r"\bscene\b", 2),
    ),
    Intent.SYSTEM: (
        (r"\b(cpu|gpu|processeur|ram|swap)\b", 3),
        (r"\b(memoire vive|espace disque|disque dur|ssd|batterie|ventilateurs?)\b", 3),
        (r"\b(processus|charge systeme|utilisation|monitoring)\b", 2),
        (r"\btemperature du (mac|processeur|cpu|gpu|systeme)\b", 3),
        (r"\b(mon mac|l'ordinateur|mon ordinateur|le systeme)\b", 1),
    ),
    Intent.SCHEDULE: (
        (r"\b(rappelle[- ]moi|rappel|remind me|reminder)\b", 3),
        (r"\b(agenda|calendrier|rendez[- ]vous|rdv|reunion|meeting)\b", 3),
        (r"\b(reveil|alarme|minuteur|timer|planifie|programme un)\b", 3),
        (r"\b(demain|ce soir|lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\b", 1),
        (r"\b\d{1,2} ?h(\d{2})?\b", 1),
    ),
    Intent.COMMUNICATION: (
        (r"\b(e-?mails?|mails?|courriels?|sms|imessage|whatsapp|slack|telegram)\b", 3),
        (r"\b(envoie|envoyer|ecris a|reponds a|repondre a|transfere|send)\b", 2),
        (r"\b(appelle|telephone a|message a|messages?)\b", 2),
    ),
    Intent.CODE: (
        (r"\b(code|python|javascript|typescript|rust|swift|script|fonction|classe|regex)\b", 3),
        (r"\b(bug|debug|debogue|stack ?trace|exception|compile|refactor\w*|commit\w*|git|pull request)\b", 3),
        (r"\b(test unitaire|tests unitaires|pytest|programme)\b", 2),
    ),
    Intent.RESEARCH: (
        (r"\b(cherche|recherche|trouve|search|look up)\b", 3),
        (r"\b(qui est|qui etait|qu'est-ce que|qu'est ce que|c'est quoi|what is|who is)\b", 2),
        (r"\b(meteo|weather|actualites?|news|definition|explique|compare)\b", 3),
        (r"\b(combien|pourquoi|comment fonctionne)\b", 1),
    ),
    Intent.CONVERSATION: (
        (r"\b(bonjour|bonsoir|salut|coucou|hello|merci|thanks)\b", 2),
        (r"\b(comment (vas[- ]tu|allez[- ]vous)|ca va|blague|raconte)\b", 2),
    ),
}
_COMPILED = {intent: tuple((re.compile(p), w) for p, w in rules) for intent, rules in _RULES.items()}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.replace("’", "'")
    return re.sub(r"\s+", " ", text).strip()


class KeywordIntentClassifier:
    """Score pondéré par intention ; confiance = part du meilleur score × saturation."""

    def __init__(self, min_confidence: float = 0.3) -> None:
        self.min_confidence = min_confidence

    def classify(self, text: str) -> Classification:
        norm = normalize(text)
        if not norm:
            return Classification(Intent.CONVERSATION, 0.0)
        scores: dict[Intent, int] = {}
        hits: dict[Intent, list[str]] = {}
        for intent, rules in _COMPILED.items():
            for pattern, weight in rules:
                for m in pattern.finditer(norm):
                    scores[intent] = scores.get(intent, 0) + weight
                    hits.setdefault(intent, []).append(m.group(0))
        if not scores:
            return Classification(Intent.CONVERSATION, 0.5)
        best = max(scores, key=lambda i: scores[i])   # ex aequo : ordre de l'enum
        top, total = scores[best], sum(scores.values())
        confidence = round((top / total) * min(1.0, top / 3), 3)
        if confidence < self.min_confidence:
            return Classification(Intent.CONVERSATION, confidence, tuple(hits[best]))
        return Classification(best, confidence, tuple(hits[best]))


class Conductor:
    """Orchestrateur unique : classe le message, choisit l'agent, passe les actions aux guardrails."""

    def __init__(
        self,
        classifier: IntentClassifier | None = None,
        guardrails: GuardrailsEngine | None = None,
        audit: AuditLog | None = None,
    ) -> None:
        self.classifier = classifier or KeywordIntentClassifier()
        self.guardrails = guardrails or GuardrailsEngine(audit=audit)
        self.audit = audit
        self._log = get_logger("friday.conductor")

    def handle(self, text: str, source: str = "text") -> RoutingDecision:
        c = self.classifier.classify(text)
        decision = RoutingDecision(c.intent, AGENT_BY_INTENT[c.intent], c.confidence, c.matched)
        fields = {
            "source": source,
            "intent": c.intent.value,
            "agent": decision.agent,
            "confidence": c.confidence,
            # Pas de texte brut dans les journaux : empreinte seulement.
            "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
        }
        self._log.info("conductor.intent", **fields)
        if self.audit is not None:
            self.audit.append("conductor", "intent.classified", fields)
        return decision

    def check_action(self, action: Action) -> Verdict:
        return self.guardrails.evaluate(action)
