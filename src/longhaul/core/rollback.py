"""Undo a day.

Every completed task leaves an annotated tag, so "put it back how it was before
day 7" is a real operation rather than a manual reset someone performs at 2am
having already lost track of what changed.

Rollback is destructive by definition, so the default is to describe what it
would do and change nothing. The `state.json` entries for rolled-back tasks are
reset to pending, which means the next `longhaul run` will attempt them again —
that is usually the point.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..schema.plan import Plan
from ..schema.state import PENDING, State
from .gitops import tag_name
from .worktree import git


@dataclass
class Rollback:
    target: str | None = None
    sha: str | None = None
    tasks: list[str] = field(default_factory=list)
    tags_removed: list[str] = field(default_factory=list)
    applied: bool = False
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def tasks_from_day(plan: Plan, day: int) -> list[str]:
    """Every task scheduled on `day` or later — rolling back day 7 undoes 7+."""
    return [t.id for t in sorted(plan.tasks, key=lambda t: (t.day, t.id)) if t.day >= day]


def _last_tag_before(plan: Plan, day: int, root: Path) -> str | None:
    """The newest checkpoint from a day earlier than this one."""
    earlier = [t for t in plan.tasks if t.day < day]
    for task in sorted(earlier, key=lambda t: (t.day, t.id), reverse=True):
        name = tag_name(task.id)
        if git("tag", "--list", name, cwd=root, check=False).strip():
            return name
    return None


def plan_rollback(plan: Plan, state: State, day: int, root: Path) -> Rollback:
    result = Rollback()

    if day < 1 or day > plan.target_days:
        result.problems.append(f"day {day} is outside 1..{plan.target_days}")
        return result

    result.tasks = tasks_from_day(plan, day)
    if not result.tasks:
        result.problems.append(f"no tasks scheduled on day {day} or later")
        return result

    target = _last_tag_before(plan, day, root)
    if target is None:
        result.problems.append(
            f"no completed checkpoint before day {day} — there is nothing to go back to. "
            "Use git directly if you mean to discard everything."
        )
        return result

    result.target = target
    result.sha = git("rev-list", "-n", "1", target, cwd=root, check=False) or None
    result.tags_removed = [
        tag_name(t) for t in result.tasks
        if git("tag", "--list", tag_name(t), cwd=root, check=False).strip()
    ]
    return result


def apply(result: Rollback, state: State, root: Path) -> Rollback:
    """Reset the branch, drop the checkpoints, and mark the tasks pending again."""
    if not result.ok or not result.target:
        return result

    git("reset", "--hard", result.target, cwd=root)
    for name in result.tags_removed:
        git("tag", "-d", name, cwd=root, check=False)

    for task_id in result.tasks:
        ts = state.tasks.get(task_id)
        if ts is None:
            continue
        ts.status = PENDING
        ts.attempts = 0
        ts.finished_at = None
        ts.last_error = None
        ts.findings = []
        ts.error_fingerprints = []
        ts.commit_sha = ts.pr_number = ts.pr_url = ts.ci_run_id = None

    result.applied = True
    return result
