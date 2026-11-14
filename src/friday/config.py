"""Chargement de la configuration YAML."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "friday.yaml"


@dataclass(frozen=True)
class GuardrailsConfig:
    actions: dict[str, int] = field(default_factory=dict)
    allowed_domains: tuple[str, ...] = ()


@dataclass(frozen=True)
class FridayConfig:
    name: str = "FRIDAY"
    master: str = ""
    language: str = "fr-FR"
    soul_path: Path = PROJECT_ROOT / "SOUL.md"
    log_level: str = "INFO"
    log_json: bool = True
    audit_db_path: Path = PROJECT_ROOT / "data" / "audit.db"
    min_confidence: float = 0.3
    guardrails: GuardrailsConfig = field(default_factory=GuardrailsConfig)
    voice_binary: Path = PROJECT_ROOT / "voice" / ".build" / "release" / "friday-voice"
    voice_locale: str = "fr-FR"
    brain_engine: str = "claude-code"          # claude-code | local
    claude_binary: str | None = None           # None : recherche automatique
    claude_model: str = "sonnet"
    claude_timeout_s: float = 60
    memory_model: str = "haiku"                # extraction des faits (appel séparé, rapide)
    default_city: str | None = None            # ville de la météo quand l'utilisateur n'en donne pas


def _resolve(path: str | Path, base: Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else base / p


def load_config(path: str | Path | None = None) -> FridayConfig:
    """Charge le YAML ; les chemins relatifs sont résolus depuis la racine du projet."""
    cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
    raw: dict[str, Any] = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    app = raw.get("app", {})
    log = raw.get("logging", {})
    audit = raw.get("audit", {})
    cond = raw.get("conductor", {})
    gr = raw.get("guardrails", {})
    voice = raw.get("voice", {})
    brain = raw.get("brain", {})

    tiers = {str(k): int(v) for k, v in (gr.get("actions") or {}).items()}
    for name, tier in tiers.items():
        if not 1 <= tier <= 4:
            raise ValueError(f"Tier invalide pour {name!r} : {tier} (attendu 1 à 4, le Tier 0 n'est pas configurable)")

    return FridayConfig(
        name=app.get("name", "FRIDAY"),
        master=app.get("master", ""),
        language=app.get("language", "fr-FR"),
        soul_path=_resolve(app.get("soul_path", "SOUL.md"), PROJECT_ROOT),
        log_level=str(log.get("level", "INFO")).upper(),
        log_json=bool(log.get("json", True)),
        audit_db_path=_resolve(audit.get("db_path", "data/audit.db"), PROJECT_ROOT),
        min_confidence=float(cond.get("min_confidence", 0.3)),
        guardrails=GuardrailsConfig(
            actions=tiers,
            allowed_domains=tuple(gr.get("allowed_domains") or ()),
        ),
        voice_binary=_resolve(voice.get("binary", "voice/.build/release/friday-voice"), PROJECT_ROOT),
        voice_locale=voice.get("locale", "fr-FR"),
        brain_engine=str(brain.get("engine", "claude-code")),
        claude_binary=brain.get("claude_binary"),
        claude_model=str(brain.get("model", "sonnet")),
        claude_timeout_s=float(brain.get("timeout_s", 60)),
        memory_model=str(brain.get("memory_model", "haiku")),
        default_city=(raw.get("tools") or {}).get("default_city"),
    )
