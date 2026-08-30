"""Ceilings, loop detection, and the decision to stop.

The role the spec called out as the one people forget, and the one that stops a
runaway agent looping on the same broken test for six hours.

Everything here is enforced *outside* the agent. Asking a model to respect a
budget produces a model that says it respected the budget.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date

from ..schema.config import Config
from ..schema.plan import Task
from ..schema.state import State, TaskState

#: Volatile fragments that make two runs of the *same* failure look different:
#: temp paths, durations, addresses, timestamps, git SHAs.
#:
#: Deliberately **not** "every number". Stripping bare digits makes
#: `expected 1, got 2` and `expected 3, got 4` identical, so an agent making
#: real progress across attempts would be halted as though it were looping.
#: Over-normalising here is worse than under-normalising: a missed loop costs a
#: retry, a false loop costs the task.
NOISE = (
    re.compile(r"/tmp/[^\s'\"]+"),
    re.compile(r"0x[0-9a-f]+"),
    re.compile(r"\b\d+(?:\.\d+)?\s*(?:s|ms|sec|seconds?)\b"),
    re.compile(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}\S*"),
    re.compile(r"\b[0-9a-f]{7,40}\b"),
    re.compile(r"\bpid[= ]\d+", re.I),
)


def fingerprint(error: str | None) -> str:
    """A stable id for a failure, so 'the same error again' is detectable."""
    if not error:
        return ""
    text = error.strip()
    for pattern in NOISE:
        text = pattern.sub("·", text)
    return hashlib.sha256(" ".join(text.split()).encode()).hexdigest()[:16]


@dataclass(frozen=True)
class Halt:
    reason: str
    scope: str  # "task" | "project"


def spent_today(state: State, today: str | None = None) -> float:
    today = today or date.today().isoformat()
    return round(
        sum(
            t.cost_usd
            for t in state.tasks.values()
            if (t.finished_at or t.started_at or "").startswith(today)
        ),
        4,
    )


def check_before(state: State, ts: TaskState, task: Task, config: Config) -> Halt | None:
    """Refuse to start work that a ceiling has already ruled out."""
    limits = config.limits

    if state.total_cost_usd >= limits.cost_usd_total:
        return Halt(
            f"project ceiling reached: ${state.total_cost_usd:.2f} of "
            f"${limits.cost_usd_total:.2f} spent",
            "project",
        )

    today = spent_today(state)
    if today >= limits.cost_usd_per_day:
        return Halt(
            f"daily ceiling reached: ${today:.2f} of ${limits.cost_usd_per_day:.2f} spent today",
            "project",
        )

    if ts.cost_usd >= limits.cost_usd_per_task:
        return Halt(
            f"{task.id} has cost ${ts.cost_usd:.2f} of its "
            f"${limits.cost_usd_per_task:.2f} allowance",
            "task",
        )

    if ts.attempts >= limits.max_attempts:
        return Halt(
            f"{task.id} has used all {limits.max_attempts} attempts", "task"
        )

    repeats = _consecutive_identical(ts)
    if repeats >= limits.identical_failures:
        return Halt(
            f"{task.id} failed with the same error {repeats} times running — "
            "retrying a deterministic failure only spends money",
            "task",
        )
    return None


def record_failure(ts: TaskState, error: str | None) -> None:
    ts.error_fingerprints.append(fingerprint(error))


def _consecutive_identical(ts: TaskState) -> int:
    prints = [p for p in ts.error_fingerprints if p]
    if not prints:
        return 0
    last = prints[-1]
    count = 0
    for value in reversed(prints):
        if value != last:
            break
        count += 1
    return count
