"""Tiers de permission et types partagés du GuardrailsEngine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from types import MappingProxyType
from typing import Any, Generic, Mapping, TypeVar

T = TypeVar("T")


class Tier(IntEnum):
    """Plus le numéro est bas, plus l'action est sensible."""

    FORBIDDEN = 0    # Interdit — BLOCK permanent
    DESTRUCTIVE = 1  # Destructif / irréversible — confirmation explicite
    MUTATION = 2     # Mutation — notifier puis exécuter
    READ_ONLY = 3    # Lecture seule — auto-approuvé + log
    INTERNAL = 4     # Interne — silencieux + log


class Approval(str, Enum):
    BLOCK = "block"
    CONFIRM = "confirm"
    NOTIFY = "notify"
    AUTO = "auto"
    SILENT = "silent"


APPROVAL_BY_TIER: Mapping[Tier, Approval] = MappingProxyType({
    Tier.FORBIDDEN: Approval.BLOCK,
    Tier.DESTRUCTIVE: Approval.CONFIRM,
    Tier.MUTATION: Approval.NOTIFY,
    Tier.READ_ONLY: Approval.AUTO,
    Tier.INTERNAL: Approval.SILENT,
})


@dataclass(frozen=True)
class Tainted(Generic[T]):
    """Valeur issue d'une source non fiable (web, e-mail, nom d'entité…)."""

    value: T
    source: str = "unknown"


@dataclass(frozen=True)
class Action:
    """Action qu'un agent veut exécuter, décrite pour le GuardrailsEngine."""

    name: str                                   # ex. "file.delete"
    params: Mapping[str, Any] = field(default_factory=dict)
    actor: str = "conductor"
    destination: str | None = None              # hôte ou URL si l'action sort du processus
    data_label: str = "public"                  # public | private | secret
    reads_private_data: bool = False
    has_untrusted_input: bool = False
    external_communication: bool = False
    code: str | None = None                     # code à exécuter, s'il y en a
    target_path: str | None = None              # fichier visé, s'il y en a
    send_as: str | None = None                  # identité d'expéditeur demandée

    @property
    def untrusted(self) -> bool:
        return self.has_untrusted_input or any(isinstance(v, Tainted) for v in self.params.values())


@dataclass(frozen=True)
class Verdict:
    action: Action
    tier: Tier
    approval: Approval
    reasons: tuple[str, ...] = ()
    rule_id: str | None = None

    @property
    def blocked(self) -> bool:
        return self.approval is Approval.BLOCK

    @property
    def requires_confirmation(self) -> bool:
        return self.approval is Approval.CONFIRM
