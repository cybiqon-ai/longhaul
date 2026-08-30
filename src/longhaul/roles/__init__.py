"""Agent role prompts, shipped as package data."""

from __future__ import annotations

from pathlib import Path

DIR = Path(__file__).parent


def load(name: str) -> str:
    path = DIR / f"{name}.md"
    if not path.is_file():
        raise FileNotFoundError(f"no prompt for role {name!r} at {path}")
    return path.read_text(encoding="utf-8")
