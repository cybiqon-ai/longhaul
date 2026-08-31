"""`.longhaul/config.yml` — the knobs, with safe defaults.

Every limit here is enforced by the orchestrator, never by asking an agent to
police itself. An agent that has been told to watch its own spend is an agent
that will report having watched its own spend.

The file is optional; the defaults below are what an unconfigured project gets,
and they are deliberately conservative. `auto_merge` is false and there is no
supported way to make it true yet.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml

CONFIG_PATH = Path(".longhaul/config.yml")


@dataclass
class Limits:
    #: Attempts at one task before it is abandoned.
    max_attempts: int = 3
    #: Identical consecutive failures before the task is halted rather than
    #: retried. Retrying a deterministic failure is how a budget is burned.
    identical_failures: int = 2
    cost_usd_per_task: float = 5.0
    cost_usd_per_day: float = 20.0
    cost_usd_total: float = 200.0
    minutes_per_task: int = 60


@dataclass
class Notify:
    #: "telegram" or "none". Credentials come from the environment, never here.
    backend: str = "none"
    #: Send a message on every task, or only on failures and decisions.
    on_success: bool = True


@dataclass
class Config:
    profile: str = ""
    base_branch: str = "main"
    push: bool = True
    #: The single biggest trust decision in the project. There is no supported
    #: way to turn this on yet, and it will need an explicit per-repo opt-in.
    auto_merge: bool = False
    #: Show the proof artefact to a model and have it judge against the
    #: criteria. Costs one extra call per task; off makes proof mechanical only.
    inspect_proof: bool = True
    #: Fast-forward `base_branch` onto each finished task's branch, so the next
    #: day builds on the last one. Without it every day branches from the same
    #: starting commit and the project never accumulates — which is what
    #: happened before this existed. The pull request stays the review artefact;
    #: `longhaul rollback` is how a day is taken back.
    integrate: bool = True
    limits: Limits = field(default_factory=Limits)
    notify: Notify = field(default_factory=Notify)

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> Config:
        d = d or {}
        known = {f.name for f in fields(cls)} - {"limits", "notify"}
        return cls(
            **{k: v for k, v in d.items() if k in known},
            limits=Limits(**_subset(d.get("limits"), Limits)),
            notify=Notify(**_subset(d.get("notify"), Notify)),
        )

    @classmethod
    def load(cls, root: Path | None = None) -> Config:
        path = (root or Path.cwd()) / CONFIG_PATH
        if not path.is_file():
            return cls()
        return cls.from_dict(yaml.safe_load(path.read_text(encoding="utf-8")))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _subset(d: Any, cls: type) -> dict[str, Any]:
    if not isinstance(d, dict):
        return {}
    known = {f.name for f in fields(cls)}
    return {k: v for k, v in d.items() if k in known}
