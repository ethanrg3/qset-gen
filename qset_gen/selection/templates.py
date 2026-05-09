"""TOML template loader — plan §7."""

from __future__ import annotations

import tomllib
from pathlib import Path

from ..models import SetTemplate


def load_template(name: str, templates_dir: Path) -> SetTemplate:
    """Load a template by name (without .toml). Raises FileNotFoundError if missing."""
    path = templates_dir / f"{name}.toml"
    if not path.exists():
        raise FileNotFoundError(f"template not found: {path}")
    with path.open("rb") as f:
        data = tomllib.load(f)
    return SetTemplate(**data)


def list_templates(templates_dir: Path) -> list[str]:
    return sorted(p.stem for p in templates_dir.glob("*.toml"))
