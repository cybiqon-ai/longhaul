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
from ..gates import proof as proof_gate
from ..gates.cheat import CheatGate
from ..gates.provenance import ProvenanceGate
from ..gates.secrets import SecretsGate
from ..schema.config import Config
from ..schema.plan import Plan, Task
from ..schema.state import DONE, FAILED, HALTED, IN_PROGRESS, PARKED, State, now
from . import devops, gitops, supervisor, transcript, worktree
from . import inspect as inspect_mod
from . import state as state_io

DEFAULT_MAX_ATTEMPTS = 3


def CliDriverRetries(result) -> list[str]:  # noqa: N802 - reads as a helper
    """Transient API failures the CLI recovered from, for the ledger.

    A run that succeeded after three 429s cost wall-clock that is otherwise
    invisible, and a run that is retrying is not a run that is stuck.
    """
    from ..driver.cli_driver import CliDriver

    return CliDriver.retries(result.raw_events or [])

#: The Coder writes code and runs the project's own tooling. It does not get
#: network access or the ability to push; git operations belong to Git Ops.
CODER_TOOLS = ["Read", "Glob", "Grep", "Edit", "Write", "Bash"]

#: Which role implements a task. Everything not listed goes to the Coder.
ROLE_FOR_KIND = {"design": "designer", "asset": "assets"}


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
        if ts and ts.status in (DONE, PARKED, HALTED, "skipped"):
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
    config: Config | None = None,
    do_push: bool = True,
) -> Outcome:
    config = config or Config()
    max_attempts = config.limits.max_attempts
    ts = state.task(task.id)
    ts.day = task.day

    halt = supervisor.check_before(state, ts, task, config)
    if halt:
        ts.status = HALTED
        ts.finished_at = now()
        ts.last_error = halt.reason
        return Outcome(task, HALTED, f"halted ({halt.scope}): {halt.reason}", ts.cost_usd)

    profile = profiles.load(profile_name or config.profile or plan.profile)

    tree = worktree.create(task.id, root=root)
    ts.branch, ts.worktree = tree.branch, str(tree.path.relative_to(root))
    ts.base_sha = ts.base_sha or tree.base_sha
    ts.status = IN_PROGRESS
    ts.attempts += 1
    ts.started_at = ts.started_at or now()
    state_io.save(state, root)

    role = ROLE_FOR_KIND.get(task.kind, "coder")
    previous = ts.last_error if ts.attempts > 1 else None
    started = time.monotonic()
    transcript_path = transcript.path_for(root, task.day, task.id, role, ts.attempts)
    result = driver.run(
        AgentRequest(
            prompt=_coder_prompt(plan, task, profile, previous),
            role=role,
            cwd=str(tree.path),
            allowed_tools=CODER_TOOLS,
            append_system_prompt=roles.load(role),
            resume_session=ts.coder_session if previous else None,
            transcript_path=str(transcript_path),
        )
    )
    retries = CliDriverRetries(result)
    ts.coder_session = result.session_id or ts.coder_session
    ts.cost_usd += result.cost_usd
    state_io.append_ledger(
        {
            "at": now(),
            "task": task.id,
            "role": role,
            "attempt": ts.attempts,
            "session_id": result.session_id,
            "cost_usd": round(result.cost_usd, 4),
            "duration_s": round(time.monotonic() - started, 1),
            "ok": result.ok,
            "retries": retries,
            "transcript": str(transcript_path.relative_to(root)),
        },
        root,
    )

    if not result.ok:
        return _fail(ts, task, f"the coder failed: {result.error}", max_attempts, ts.cost_usd)

    diff = worktree.diff(tree.path, ts.base_sha or tree.base_sha)
    blocking: list[str] = []
    for gate in (CheatGate(), SecretsGate(), ProvenanceGate()):
        blocking += [str(f) for f in gate.check(diff).findings if f.severity == "block"]
    if blocking:
        ts.findings = blocking
        return _fail(
            ts, task, "blocked by the gates:\n  " + "\n  ".join(blocking),
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

    proof = _prove(driver, plan, task, tree.path, root, config, ts)
    if proof is not None:
        return proof

    ship = gitops.ship(
        plan, task, tree.path, tree.branch, root,
        do_push=do_push and config.push, base=config.base_branch,
    )
    ts.commit_sha = ship.sha
    ts.pr_number = ship.pr_number
    ts.pr_url = ship.pr_url
    ts.ci_run_id = ship.ci_run_id
    if not ship.ok:
        return _fail(ts, task, f"nothing was committed: {ship.detail}",
                     max_attempts, ts.cost_usd, report=report)

    ts.finished_at = now()
    ts.findings = []

    if task.needs_human:
        # `needs_human` means a human must *decide*, not that no work happens.
        # Every such task in a real plan asks for the material the decision
        # rests on — three palette options, a dependency comparison, a
        # difficulty curve. Parking with nothing produces nothing to decide
        # from, and blocks every dependent task behind an empty question.
        ts.status = PARKED
        ts.last_error = "the plan reserved this decision for you — the work is done and waiting"
        return Outcome(
            task, PARKED,
            f"{report.summary()} · {ship.detail} · parked for your decision",
            ts.cost_usd, report,
        )

    ts.status = DONE
    ts.last_error = None
    detail = f"{report.summary()} · {ship.detail}"
    if ts.proof_detail:
        detail = f"{report.summary()} · {ts.proof_detail} · {ship.detail}"
    return Outcome(task, DONE, detail, ts.cost_usd, report)


def _prove(driver, plan, task, worktree, root, config, ts) -> Outcome | None:
    """Run the proof step and inspect what it produced. None means "carry on".

    A proof that *could not run* is reported honestly and does not fail the
    task — a machine without an emulator has demonstrated nothing either way,
    and refusing to proceed would make the tool unusable off a CI runner. A
    proof that ran and failed does fail the task.
    """
    profile = profiles.load(config.profile or plan.profile)
    proof_dir = root / state_io.LONGHAUL_DIR / "proof" / f"day-{task.day:02d}" / task.id

    result = proof_gate.run(profile, worktree, proof_dir)
    ts.proof_kind = result.kind
    ts.proof_artifacts = [str(p.relative_to(root)) for p in result.artifacts]
    ts.proof_detail = result.summary()

    if not result.kind:
        return None
    if not result.ran:
        return None  # honest, recorded, and not a pass either
    if not result.ok:
        ts.last_error = f"{result.detail}\n\n{result.log[-4000:]}"
        return _fail(ts, task, result.summary(), config.limits.max_attempts, ts.cost_usd)

    if not config.inspect_proof:
        return None

    verdict = inspect_mod.run(driver, plan, task, result.artifacts, worktree)
    ts.cost_usd += verdict.cost_usd
    ts.proof_detail = f"{result.summary()} · {verdict.summary()}"
    if verdict.ran and not verdict.passes:
        ts.last_error = (
            f"the artefact does not show what day {task.day} claims.\n"
            f"observed: {verdict.observed}\n"
            + "\n".join(f"- {p}" for p in verdict.problems or [])
        )
        return _fail(ts, task, verdict.summary(), config.limits.max_attempts, ts.cost_usd)
    return None


def _fail(ts, task, detail, max_attempts, cost, report=None, findings=None) -> Outcome:
    ts.status = FAILED
    ts.last_error = ts.last_error or detail
    supervisor.record_failure(ts, ts.last_error)
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
    config: Config | None = None,
    do_push: bool = True,
) -> Outcome:
    task = next_task(plan, state)
    if task is None:
        return Outcome(None, "idle", "no eligible task — the plan is finished or fully blocked")
    if state.tasks.get(task.id) and state.tasks[task.id].status == DONE:
        return Outcome(task, DONE, "already done", 0.0)  # idempotent
    outcome = run_task(
        driver, plan, task, state, root, profile_name, config=config, do_push=do_push
    )
    state_io.save(state, root)
    return outcome
