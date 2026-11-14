"""Masquage des identifiants dans tout ce que Friday écrit : logs et audit.

Dernière ligne de défense : aucun appelant ne doit y mettre de secret, mais si un message
d'erreur ou un argument en contient un (clé d'API, jeton, clé privée), il est remplacé
avant d'être écrit. Les motifs sont ceux de la règle Tier 0 `T0-CREDENTIALS`.
"""

from __future__ import annotations

from typing import Any

MASK = "[secret masqué]"


def _patterns():                                      # import tardif : guardrails importe audit
    from .guardrails.tier0 import _CREDENTIAL_PATTERNS
    return _CREDENTIAL_PATTERNS


def redact_text(text: str) -> str:
    for p in _patterns():
        text = p.sub(MASK, text)
    return text


def redact(value: Any) -> Any:
    """Copie de `value` (str, dict, list, tuple) où chaque identifiant reconnu est masqué."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {redact(k) if isinstance(k, str) else k: redact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(redact(v) for v in value)
    return value


def structlog_processor(_logger: Any, _method: str, event: dict[str, Any]) -> dict[str, Any]:
    """Processeur structlog : masque les identifiants dans chaque champ d'un événement."""
    return redact(event)
