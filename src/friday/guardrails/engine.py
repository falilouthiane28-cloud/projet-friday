"""GuardrailsEngine : matrice de permissions Tier 0 à 4.

Ordre d'évaluation :
1. Règles Tier 0 codées en dur (`tier0.py`) → BLOCK, sans dérogation.
2. Tier de l'action : le plus strict entre la configuration YAML et les planchers
   codés en dur ci-dessous. La configuration peut durcir, jamais assouplir.
3. Action inconnue → Tier 1 (fermé par défaut).
4. Contamination (« CaMeL light », `taint.py`) : après lecture d'un contenu non fiable,
   une mutation (Tier 2) ou une URL chargée de données passe en confirmation (Tier 1).
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from ..audit import AuditLog
from ..log import get_logger
from .taint import escalate
from .tier0 import check_tier0
from .tiers import APPROVAL_BY_TIER, Action, Tier, Verdict

UNKNOWN_ACTION_TIER = Tier.DESTRUCTIVE

# Planchers codés en dur : ces actions ne descendent jamais sous ce tier.
TIER_FLOORS: Mapping[str, Tier] = MappingProxyType({
    "file.delete": Tier.DESTRUCTIVE,
    "file.move": Tier.DESTRUCTIVE,
    "message.send": Tier.DESTRUCTIVE,
    "email.send": Tier.DESTRUCTIVE,
    "payment.execute": Tier.DESTRUCTIVE,
    "shell.exec": Tier.DESTRUCTIVE,
    "memory.delete": Tier.DESTRUCTIVE,
    "home.secure": Tier.DESTRUCTIVE,          # serrures, alarme, garage, volets
})
DESTRUCTIVE_SUFFIXES: tuple[str, ...] = (".delete", ".remove", ".purge", ".exec", ".send", ".pay")


class GuardrailsEngine:
    def __init__(
        self,
        action_tiers: Mapping[str, int] | None = None,
        allowed_domains: tuple[str, ...] = (),
        audit: AuditLog | None = None,
    ) -> None:
        tiers: dict[str, Tier] = {}
        for name, value in (action_tiers or {}).items():
            tier = Tier(int(value))
            if tier is Tier.FORBIDDEN:
                raise ValueError("Le Tier 0 est codé en dur et ne peut pas être configuré")
            tiers[name] = tier
        self._tiers: Mapping[str, Tier] = MappingProxyType(tiers)
        self._allowed_domains = tuple(d.lower() for d in allowed_domains)
        self._audit = audit
        self._log = get_logger("friday.guardrails")

    def tier_for(self, action: Action) -> Tier:
        tier = self._tiers.get(action.name, UNKNOWN_ACTION_TIER)
        floor = TIER_FLOORS.get(action.name)
        if floor is None and action.name.endswith(DESTRUCTIVE_SUFFIXES):
            floor = Tier.DESTRUCTIVE
        if action.external_communication:
            floor = Tier.DESTRUCTIVE                  # toute sortie vers l'extérieur = approbation
        return min(tier, floor) if floor is not None else tier

    def evaluate(self, action: Action) -> Verdict:
        rule = check_tier0(action, self._allowed_domains)
        if rule is not None:
            verdict = Verdict(action, Tier.FORBIDDEN, APPROVAL_BY_TIER[Tier.FORBIDDEN], (rule.description,), rule.id)
        else:
            tier, reason = escalate(action, self.tier_for(action))
            verdict = Verdict(action, tier, APPROVAL_BY_TIER[tier], (reason,) if reason else ())
        self._record(verdict)
        return verdict

    def authorize(self, action: Action, confirmed_by_master: bool = False) -> bool:
        """True si l'action peut s'exécuter maintenant."""
        verdict = self.evaluate(action)
        if verdict.blocked:
            return False
        if verdict.requires_confirmation:
            return confirmed_by_master
        return True

    def _record(self, v: Verdict) -> None:
        fields = {
            "action": v.action.name,
            "actor": v.action.actor,
            "tier": int(v.tier),
            "approval": v.approval.value,
            "rule_id": v.rule_id,
        }
        if v.action.untrusted:
            fields["taint"] = list(v.action.taint_sources) or ["untrusted"]
        if v.blocked:
            self._log.warning("guardrails.blocked", **fields, reasons=list(v.reasons))
        else:
            self._log.info("guardrails.verdict", **fields)
        if self._audit is not None:
            self._audit.append("guardrails", "guardrails.verdict", {**fields, "reasons": list(v.reasons)})
