"""Règles Tier 0 — INVIOLABLES, codées en dur.

Ces règles ne viennent ni du prompt ni de la configuration : aucun fichier YAML,
aucune préférence et aucun agent ne peut les retirer, les assouplir ou en ajouter
une version permissive. Elles sont évaluées avant toute autre règle.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator
from urllib.parse import urlparse

from .tiers import Action, Tainted

_PKG_ROOT = Path(__file__).resolve().parents[1]      # src/friday
_PROJECT_ROOT = _PKG_ROOT.parents[1]

# Fichiers qui portent les règles de sécurité : Friday ne peut jamais les modifier.
PROTECTED_PATHS: tuple[Path, ...] = (
    _PKG_ROOT / "guardrails",
    _PKG_ROOT / "audit.py",
    _PROJECT_ROOT / "config",
    _PROJECT_ROOT / "SOUL.md",
    _PROJECT_ROOT / "data" / "audit.db",
    _PROJECT_ROOT / "data" / "memory.db",
)
PROTECTED_ACTION_PREFIXES: tuple[str, ...] = ("guardrails.", "audit.", "security.")

_CREDENTIAL_PATTERNS: tuple[re.Pattern[str], ...] = tuple(re.compile(p, re.IGNORECASE) for p in (
    r"sk-ant-[a-z0-9_\-]{10,}",                  # clé Anthropic
    r"\bsk-[a-z0-9]{20,}",                       # clés type OpenAI
    r"\bAKIA[0-9A-Z]{16}\b",                     # AWS
    r"\bgh[pousr]_[A-Za-z0-9]{20,}",             # GitHub
    r"\bxox[abprs]-[A-Za-z0-9\-]{10,}",          # Slack
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"\b(password|passwd|mot[_ ]?de[_ ]?passe|api[_\-]?key|secret|token)\s*[:=]\s*\S{4,}",
))

_OBFUSCATION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(re.compile(p, re.IGNORECASE | re.DOTALL) for p in (
    r"(exec|eval)\s*\(.*(b64decode|base64|decode\(|fromhex|unhexlify|rot13|zlib|marshal)",
    r"(b64decode|unhexlify|fromhex|marshal\.loads|zlib\.decompress).*\b(exec|eval|compile)\s*\(",
    r"__import__\s*\(\s*['\"](os|subprocess|socket)['\"]\s*\)",
    r"(curl|wget)[^|\n]*\|\s*(ba|z)?sh\b",
    r"base64\s+(-d|--decode)[^|\n]*\|\s*(ba|z)?sh\b",
    r"(\\x[0-9a-f]{2}){16,}",                    # longue chaîne en échappements hexadécimaux
    r"\beval\s+\$\(",                            # eval $(…) en shell
))


@dataclass(frozen=True)
class Tier0Rule:
    id: str
    description: str
    check: Callable[[Action, tuple[str, ...]], bool]   # True = violation


def _strings(value: Any) -> Iterator[str]:
    if isinstance(value, Tainted):
        value = value.value
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield str(k)
            yield from _strings(v)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for v in value:
            yield from _strings(v)


def _host(destination: str) -> str:
    parsed = urlparse(destination if "//" in destination else f"//{destination}")
    return (parsed.hostname or "").lower()


def _host_allowed(destination: str, allowed: tuple[str, ...]) -> bool:
    host = _host(destination)
    return any(host == d or host.endswith("." + d) for d in allowed)


def _exfiltration(a: Action, allowed: tuple[str, ...]) -> bool:
    if a.destination is None:
        return False
    if a.data_label == "secret":                 # un secret ne quitte jamais le processus
        return True
    # Donnée privée vers un hôte non autorisé hors d'une communication déclarée
    # (une communication déclarée passe en Tier 1 : confirmation du maître).
    return a.data_label == "private" and not a.external_communication and not _host_allowed(a.destination, allowed)


def _obfuscated_code(a: Action, _: tuple[str, ...]) -> bool:
    texts = [a.code] if a.code else []
    texts += list(_strings(dict(a.params)))
    return any(p.search(t) for t in texts for p in _OBFUSCATION_PATTERNS)


def _self_modification(a: Action, _: tuple[str, ...]) -> bool:
    if a.name.startswith(PROTECTED_ACTION_PREFIXES):
        return True
    if a.target_path:
        target = Path(a.target_path).expanduser()
        target = (target if target.is_absolute() else _PROJECT_ROOT / target).resolve()
        return any(target == p or p in target.parents or _sqlite_sibling(target, p) for p in PROTECTED_PATHS)
    return False


def _sqlite_sibling(target: Path, protected: Path) -> bool:
    """`audit.db-wal`, `memory.db-shm`… portent les mêmes données que la base protégée."""
    return (protected.suffix == ".db" and target.parent == protected.parent
            and target.name in {protected.name + s for s in ("-wal", "-shm", "-journal")})


def _impersonation(a: Action, _: tuple[str, ...]) -> bool:
    return a.send_as is not None and a.send_as.strip().lower() not in {"friday", "master", "maître", "maitre"}


def _plaintext_credentials(a: Action, _: tuple[str, ...]) -> bool:
    texts = list(_strings(dict(a.params))) + ([a.code] if a.code else [])
    return any(p.search(t) for t in texts for p in _CREDENTIAL_PATTERNS)


def _lethal_trifecta(a: Action, _: tuple[str, ...]) -> bool:
    return a.reads_private_data and a.untrusted and a.external_communication


TIER0_RULES: tuple[Tier0Rule, ...] = (
    Tier0Rule("T0-EXFIL", "Exfiltration de données privées ou secrètes", _exfiltration),
    Tier0Rule("T0-OBFUSCATED", "Exécution de code obfusqué", _obfuscated_code),
    Tier0Rule("T0-SELF-MODIFY", "Modification des règles de sécurité de Friday", _self_modification),
    Tier0Rule("T0-IMPERSONATION", "Usurpation d'identité", _impersonation),
    Tier0Rule("T0-CREDENTIALS", "Identifiants en clair", _plaintext_credentials),
    Tier0Rule("T0-TRIFECTA", "Lethal Trifecta : données privées + entrée non fiable + sortie externe", _lethal_trifecta),
)


def check_tier0(action: Action, allowed_domains: tuple[str, ...] = ()) -> Tier0Rule | None:
    """Retourne la première règle Tier 0 violée, ou None."""
    for rule in TIER0_RULES:
        if rule.check(action, allowed_domains):
            return rule
    return None
