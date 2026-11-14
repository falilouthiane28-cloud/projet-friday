"""Lecture de SOUL.md (identité et valeurs de Friday)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

_YAML_BLOCK = re.compile(r"```yaml\n(.*?)```", re.DOTALL)


def load_soul(path: str | Path) -> dict[str, Any]:
    """Retourne le bloc YAML de SOUL.md sous forme de dictionnaire."""
    text = Path(path).read_text(encoding="utf-8")
    match = _YAML_BLOCK.search(text)
    if not match:
        raise ValueError(f"Aucun bloc ```yaml dans {path}")
    soul = yaml.safe_load(match.group(1))
    if "IDENTITY" not in soul:
        raise ValueError("SOUL.md doit contenir une section IDENTITY")
    return soul
