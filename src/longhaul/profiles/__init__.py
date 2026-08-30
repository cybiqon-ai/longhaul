"""Per-stack build/test/lint/run commands, as YAML data.

A profile tells the DevOps role what "build" and "test" mean for a stack so it
never has to guess, and tells `doctor` which binaries must exist before day 1.
Adding one requires no Python — see docs/profiles.md.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DIR = Path(__file__).parent


def available() -> list[str]:
    return sorted(p.stem for p in DIR.glob("*.yml"))


def load(name: str) -> dict[str, Any]:
    path = DIR / f"{name}.yml"
    if not path.is_file():
        raise FileNotFoundError(f"unknown profile {name!r}; available: {', '.join(available())}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"profile {name!r} is not a mapping")
    return data


def summarise(name: str) -> str:
    """A compact description of the stack, for the Planner's prompt."""
    p = load(name)
    commands = p.get("commands") or {}
    lines = [f"Profile: {name} — {p.get('description', '')}".rstrip()]
    if p.get("requires"):
        lines.append("Required tools: " + ", ".join(p["requires"]))
    if commands:
        lines.append("Commands available to the DevOps role:")
        lines += [f"  {k}: {v}" for k, v in commands.items()]
    proof = p.get("proof") or {}
    if proof.get("kind"):
        lines.append(f"Proof for this stack is `{proof['kind']}` — a task's `proof.expect`")
        lines.append("should describe what that artifact must show.")
    return "\n".join(lines)
