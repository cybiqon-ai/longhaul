"""One day, one task.

The loop is deliberately small: pick the next eligible task, implement it in an
isolated worktree, build and test it, run the deterministic gates, record what
happened. Git operations are not here yet — nothing is committed or pushed.

Two properties matter more than anything else in this file:

*Idempotent* — running twice in a day must not do the work twice.
*Resumable* — killed at any point, the next invocation continues from
`state.json` rather than starting over. That is what makes it safe to schedule.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from .. import profiles, roles
from ..driver.base import AgentDriver, AgentRequest
from ..gates.cheat import CheatGate
from ..schema.plan import Plan, Task
from ..schema.state import DONE, FAILED, IN_PROGRESS, PARKED, State, now
from . import devops, worktree
from . import state as state_io

DEFAULT_MAX_ATTEMPTS = 3

#: The Coder writes code and runs the project's own tooling. It does not get
#: network access or the ability to push; git operations belong to Git Ops.
CODER_TOOLS = ["Read", "Glob", "Grep", "Edit", "Write", "Bash"]


@dataclass
class Outcome:
    task: Task | None
    status: str
    detail: str
    cost_usd: float = 0.0
    report: devops.BuildReport | None = None
    findings: list[str] | None = None

    @property
    def exit_code(self) -> int:
        return 0 if self.status in (DONE, PARKED, "idle") else 1


def next_task(plan: Plan, state: State) -> Task | None:
    """Lowest day first; dependencies must be settled; parked tasks are skipped.

    Deliberately does not stop at the first blocked task — one open question
    should not stall a fortnight when other work is ready.
    """
    for task in sorted(plan.tasks, key=lambda t: (t.day, t.id)):
        ts = state.tasks.get(task.id)
        if ts and ts.status in (DONE, PARKED, "skipped"):
            continue
        if ts and ts.status == FAILED and ts.attempts >= DEFAULT_MAX_ATTEMPTS:
            continue
        if all(state.is_settled(dep) for dep in task.depends_on):
            return task
    return None


def run_task(
    driver: AgentDriver,
    plan: Plan,
    task: Task,
    state: State,
    root: Path,
    profile_name: str | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> Outcome:
    ts = state.task(task.id)
    ts.day = task.day

    if task.needs_human:
        ts.status = PARKED
        ts.finished_at = now()
        ts.last_error = "the plan reserved this decision for a human"
        return Outcome(task, PARKED, "parked: the plan flagged this task needs_human")

    profile = profiles.load(profile_name or plan.profile)

    tree = worktree.create(task.id, root=root)
    ts.branch, ts.worktree = tree.branch, str(tree.path.relative_to(root))
    ts.base_sha = ts.base_sha or tree.base_sha
    ts.status = IN_PROGRESS
    ts.attempts += 1
    ts.started_at = ts.started_at or now()
    state_io.save(state, root)

    previous = ts.last_error if ts.attempts > 1 else None
    started = time.monotonic()
    result = driver.run(
        AgentRequest(
            prompt=_coder_prompt(plan, task, profile, previous),
            role="coder",
            cwd=str(tree.path),
            allowed_tools=CODER_TOOLS,
            append_system_prompt=roles.load("coder"),
            resume_session=ts.coder_session if previous else None,
        )
    )
    ts.coder_session = result.session_id or ts.coder_session
    ts.cost_usd += result.cost_usd
    state_io.append_ledger(
        {
            "at": now(),
            "task": task.id,
            "role": "coder",
            "attempt": ts.attempts,
            "session_id": result.session_id,
            "cost_usd": round(result.cost_usd, 4),
            "duration_s": round(time.monotonic() - started, 1),
            "ok": result.ok,
        },
        root,
    )

    if not result.ok:
        return _fail(ts, task, f"the coder failed: {result.error}", max_attempts, ts.cost_usd)

    diff = worktree.diff(tree.path, ts.base_sha or tree.base_sha)
    gate = CheatGate().check(diff)
    blocking = [str(f) for f in gate.findings if f.severity == "block"]
    if blocking:
        ts.findings = blocking
        return _fail(
            ts, task, "blocked by the cheat gate:\n  " + "\n  ".join(blocking),
            max_attempts, ts.cost_usd, findings=blocking,
        )
    if not diff.strip():
        return _fail(ts, task, "the coder changed nothing", max_attempts, ts.cost_usd)

    report = devops.run(profile, tree.path)
    if not report.ok:
        ts.last_error = report.feedback()
        return _fail(
            ts, task, f"build/test failed: {report.summary()}", max_attempts, ts.cost_usd,
            report=report,
        )

    ts.status = DONE
    ts.finished_at = now()
    ts.last_error = None
    ts.findings = []
    return Outcome(task, DONE, report.summary(), ts.cost_usd, report)


def _fail(ts, task, detail, max_attempts, cost, report=None, findings=None) -> Outcome:
    ts.status = FAILED
    ts.last_error = ts.last_error or detail
    ts.finished_at = now()
    if ts.attempts >= max_attempts:
        detail += f"\nretry budget exhausted ({ts.attempts}/{max_attempts}) — halting this task"
    return Outcome(task, FAILED, detail, cost, report, findings)


def _coder_prompt(plan: Plan, task: Task, profile: dict, previous_error: str | None) -> str:
    lines = [
        f"Project: {plan.project}",
        f"Day {task.day} of {plan.target_days}.",
        "",
        f"## Task {task.id} — {task.title}",
        "",
        "Acceptance criteria (you are judged against exactly these):",
        *[f"  - {c}" for c in task.acceptance_criteria],
    ]
    if task.proof and task.proof.expect:
        lines += ["", f"Proof for this day: {task.proof.kind} — {task.proof.expect}"]
    commands = profile.get("commands") or {}
    if commands:
        lines += ["", "## Run these yourself before you finish", ""]
        lines += [f"  {k}: {v}" for k, v in commands.items() if k != "test_count"]
    if previous_error:
        lines += [
            "",
            "## This is a retry. Your previous attempt failed with:",
            "",
            previous_error[:6000],
            "",
            "Fix the cause. Do not weaken the check that caught it.",
        ]
    return "\n".join(lines)


def run_day(
    driver: AgentDriver,
    plan: Plan,
    state: State,
    root: Path,
    profile_name: str | None = None,
) -> Outcome:
    task = next_task(plan, state)
    if task is None:
        return Outcome(None, "idle", "no eligible task — the plan is finished or fully blocked")
    if state.tasks.get(task.id) and state.tasks[task.id].status == DONE:
        return Outcome(task, DONE, "already done", 0.0)  # idempotent
    outcome = run_task(driver, plan, task, state, root, profile_name)
    state_io.save(state, root)
    return outcome
