"""The `state.json` contract — what has happened, as opposed to what is planned.

`plan.yaml` is written once and read for a fortnight; `state.json` is rewritten
after every step. Between them they are the whole memory of a run: kill the
process at any point and the next invocation resumes from what is on disk rather
than from scratch.

Everything here is deliberately plain and human-readable, because this file is
committed to the target repository and the first thing anyone debugging a stuck
project will open.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

PENDING = "pending"
IN_PROGRESS = "in_progress"
DONE = "done"
FAILED = "failed"
PARKED = "parked"
SKIPPED = "skipped"

STATUSES = (PENDING, IN_PROGRESS, DONE, FAILED, PARKED, SKIPPED)

#: Statuses a task will never leave on its own. `failed` is absent on purpose:
#: it is retryable up to the attempt budget, and `parked` needs a human.
TERMINAL = (DONE, SKIPPED)


def now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


@dataclass
class TaskState:
    id: str
    status: str = PENDING
    attempts: int = 0
    day: int | None = None
    branch: str | None = None
    worktree: str | None = None
    base_sha: str | None = None
    coder_session: str | None = None
    cost_usd: float = 0.0
    started_at: str | None = None
    finished_at: str | None = None
    last_error: str | None = None
    #: Human-readable one-liners; the full detail lives in .longhaul/runs/.
    findings: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TaskState:
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "attempts": self.attempts,
            "day": self.day,
            "branch": self.branch,
            "worktree": self.worktree,
            "base_sha": self.base_sha,
            "coder_session": self.coder_session,
            "cost_usd": round(self.cost_usd, 4),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "last_error": self.last_error,
            "findings": list(self.findings),
        }


@dataclass
class State:
    project: str = ""
    created_at: str = field(default_factory=now)
    updated_at: str = field(default_factory=now)
    tasks: dict[str, TaskState] = field(default_factory=dict)

    def task(self, task_id: str) -> TaskState:
        """Tasks are created lazily, so a plan can gain tasks on a re-plan."""
        if task_id not in self.tasks:
            self.tasks[task_id] = TaskState(id=task_id)
        return self.tasks[task_id]

    def is_settled(self, task_id: str) -> bool:
        return self.tasks.get(task_id, TaskState(id=task_id)).status in TERMINAL

    def counts(self) -> dict[str, int]:
        """Report a count, not a status."""
        out = dict.fromkeys(STATUSES, 0)
        for t in self.tasks.values():
            out[t.status] = out.get(t.status, 0) + 1
        return out

    @property
    def total_cost_usd(self) -> float:
        return round(sum(t.cost_usd for t in self.tasks.values()), 4)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> State:
        if not isinstance(d, dict):
            raise ValueError("state.json is not a mapping")
        tasks = {k: TaskState.from_dict(v) for k, v in (d.get("tasks") or {}).items()}
        bad = [t.id for t in tasks.values() if t.status not in STATUSES]
        if bad:
            raise ValueError(f"unknown status on task(s): {', '.join(bad)}")
        return cls(
            project=str(d.get("project", "")),
            created_at=str(d.get("created_at") or now()),
            updated_at=str(d.get("updated_at") or now()),
            tasks=tasks,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": self.project,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "total_cost_usd": self.total_cost_usd,
            "tasks": {k: v.to_dict() for k, v in self.tasks.items()},
        }
