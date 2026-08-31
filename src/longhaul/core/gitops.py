"""Commit, push, open a pull request — and verify CI actually ran.

Like DevOps, this is deterministic rather than an agent. A conventional commit
message is derivable from the task and its acceptance criteria; asking a model
to write one spends money to produce something less consistent.

**The important part of this file is `verify_ci_started`.** GitHub does not
trigger workflows on commits pushed with the default `GITHUB_TOKEN`. A pipeline
that pushes with it gets green PRs and a CI system that never ran — no error, no
warning, nothing to notice. "CI is the source of truth" then quietly means
nothing checked anything. So Longhaul asks, every time, whether a run exists for
the SHA it just pushed, and treats "no" as a failure rather than as silence.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from ..integrations.github import GitHub, GitHubError, parse_remote
from ..schema.plan import Plan, Task
from .worktree import git

CI_START_GRACE_S = 90
CI_POLL_INTERVAL_S = 15


def tag_name(task_id: str) -> str:
    return f"longhaul/done/{task_id}"


def tag(worktree: Path, task_id: str, message: str) -> str | None:
    """Mark a completed task so `longhaul rollback` has somewhere to go back to.

    Annotated, so the tag carries who and when. Never overwrites an existing
    tag: re-running a finished day must not silently move a checkpoint someone
    may already have rolled back to.
    """
    name = tag_name(task_id)
    if git("tag", "--list", name, cwd=worktree, check=False).strip():
        return name
    git("tag", "-a", name, "-m", message, cwd=worktree)
    return name


@dataclass
class Integration:
    """Whether the day's work landed on the base branch."""

    advanced: bool = False
    from_sha: str | None = None
    to_sha: str | None = None
    detail: str = ""


@dataclass
class PushResult:
    committed: bool = False
    sha: str | None = None
    tag: str | None = None
    pushed: bool = False
    pr_number: int | None = None
    pr_url: str | None = None
    ci_run_id: int | None = None
    ci_conclusion: str | None = None
    ci_jobs: int = 0
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.committed


def commit_message(plan: Plan, task: Task) -> str:
    """Conventional commit, derived from the task rather than invented."""
    kind = {"feature": "feat", "fix": "fix", "docs": "docs",
            "infra": "chore", "design": "feat", "asset": "chore"}.get(task.kind, "chore")
    subject = f"{kind}({task.id}): {task.title}"
    if len(subject) > 72:
        subject = subject[:69] + "..."
    body = [
        "",
        f"Day {task.day} of {plan.target_days}.",
        "",
        "Acceptance criteria this change is judged against:",
        *[f"  - {c}" for c in task.acceptance_criteria],
        "",
        "Written by Longhaul. Gates passed before this commit was made: the diff",
        "was checked for disabled tests, weakened configuration and credentials,",
        "and the project's own build, lint and test commands were run against it.",
    ]
    return subject + "\n" + "\n".join(body) + "\n"


def commit(worktree: Path, message: str) -> str | None:
    """Stage and commit everything in the worktree. Returns the SHA, or None."""
    git("add", "-A", cwd=worktree)
    if not git("status", "--porcelain", cwd=worktree, check=False).strip():
        head = git("rev-parse", "HEAD", cwd=worktree, check=False)
        return head or None
    git("commit", "-q", "-m", message, cwd=worktree)
    return git("rev-parse", "HEAD", cwd=worktree)


def push(worktree: Path, branch: str, remote: str = "origin") -> None:
    git("push", "-u", remote, branch, cwd=worktree)


def remote_url(root: Path, remote: str = "origin") -> str | None:
    url = git("remote", "get-url", remote, cwd=root, check=False)
    return url or None


def verify_ci_started(
    client: GitHub, sha: str, grace_s: int = CI_START_GRACE_S, sleep=time.sleep
) -> tuple[int | None, str]:
    """Did a workflow run actually start for this commit?

    Returns (run_id, explanation). A `None` run_id when the repository *has*
    workflows is a failure, not a quiet pass — most often it means the push was
    made with a token whose events do not trigger Actions.
    """
    deadline = time.monotonic() + grace_s
    while True:
        runs = client.runs_for_sha(sha)
        if runs:
            return runs[0]["id"], f"CI run {runs[0]['id']} started"
        if time.monotonic() >= deadline:
            break
        sleep(CI_POLL_INTERVAL_S)

    if not client.has_workflows():
        return None, "no workflows in this repository — nothing to verify"
    return None, (
        f"no CI run appeared for {sha[:12]} within {grace_s}s, but this repository "
        "has workflows. A push made with the default GITHUB_TOKEN does not trigger "
        "them — use a GitHub App token or a PAT."
    )


def wait_for_ci(
    client: GitHub, run_id: int, timeout_s: int = 1800, sleep=time.sleep
) -> tuple[str, int]:
    """Block until the run completes. Returns (conclusion, jobs that ran).

    The job count matters: a run can conclude 'success' having executed nothing,
    which is what an unparseable workflow file looks like from the outside.
    """
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        run = client.get_run(run_id)
        if run.get("status") == "completed":
            jobs = client.jobs_for_run(run_id)
            return run.get("conclusion") or "unknown", len(jobs)
        sleep(CI_POLL_INTERVAL_S)
    return "timed_out", 0


def ship(
    plan: Plan,
    task: Task,
    worktree: Path,
    branch: str,
    root: Path,
    *,
    do_push: bool = True,
    base: str = "main",
    open_pr: bool = True,
    wait: bool = False,
) -> PushResult:
    result = PushResult()
    result.sha = commit(worktree, commit_message(plan, task))
    result.committed = bool(result.sha)
    if not result.committed:
        result.detail = "nothing to commit"
        return result

    result.tag = tag(worktree, task.id, f"day {task.day}: {task.title}")

    if not do_push:
        result.detail = f"committed {result.sha[:12]} on {branch} (not pushed)"
        return result

    url = remote_url(root)
    if not url:
        result.detail = f"committed {result.sha[:12]}; no remote configured, so nothing pushed"
        return result

    push(worktree, branch)
    result.pushed = True

    try:
        owner, repo = parse_remote(url)
        client = GitHub(owner, repo)
    except GitHubError as exc:
        result.detail = f"pushed {branch}, but GitHub is unreachable: {exc}"
        return result

    if open_pr:
        pr = client.open_pull_request(
            head=branch,
            base=base,
            title=commit_message(plan, task).splitlines()[0],
            body=_pr_body(plan, task),
        )
        result.pr_number, result.pr_url = pr.number, pr.url

    run_id, explanation = verify_ci_started(client, result.sha)
    result.ci_run_id = run_id
    result.detail = explanation

    if run_id and wait:
        result.ci_conclusion, result.ci_jobs = wait_for_ci(client, run_id)
        result.detail = f"CI {result.ci_conclusion} across {result.ci_jobs} job(s)"
    return result


def integrate(root: Path, branch: str, base: str = "main") -> Integration:
    """Fast-forward the base branch onto a finished task's branch.

    Without this, every day branches from the same starting commit and none of
    them can see the day before — four parallel universes, each rebuilding the
    scaffold from nothing, while every gate passes and the status line reports
    progress. That happened on the first real multi-day run.

    The design assumed a human merging pull requests. With `auto_merge` off and
    no remote, nothing ever lands, so the base has to advance locally. The pull
    request stays the review artefact, and `longhaul rollback` is how a day gets
    taken back.

    Fast-forward only. If the base has moved independently this refuses and says
    so rather than merging: quietly resolving that is how work gets lost.
    """
    result = Integration()

    current = git("rev-parse", "--abbrev-ref", "HEAD", cwd=root, check=False)
    if current != base:
        result.detail = f"the repository is on '{current}', not '{base}' — not touching it"
        return result

    dirty = [
        line for line in git("status", "--porcelain", cwd=root, check=False).splitlines()
        if line and not line.startswith("??")
    ]
    if dirty:
        result.detail = f"{len(dirty)} uncommitted change(s) on {base} — not merging over them"
        return result

    result.from_sha = git("rev-parse", base, cwd=root, check=False)
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", base, branch],
        cwd=root, capture_output=True, timeout=60,
    )
    if ancestor.returncode != 0:
        result.detail = (
            f"{base} is not an ancestor of {branch} — it moved independently, "
            "so this needs a human rather than a merge"
        )
        return result

    git("merge", "--ff-only", branch, cwd=root)
    result.to_sha = git("rev-parse", base, cwd=root, check=False)
    result.advanced = result.to_sha != result.from_sha
    result.detail = (
        f"{base} → {result.to_sha[:12]}" if result.advanced
        else f"{base} already contained {branch}"
    )
    return result


def _pr_body(plan: Plan, task: Task) -> str:
    lines = [
        f"**Day {task.day} of {plan.target_days}** — {plan.project}",
        "",
        "### Acceptance criteria",
        *[f"- [ ] {c}" for c in task.acceptance_criteria],
        "",
        "### What ran before this PR existed",
        "- cheat gate: no disabled tests, no weakened configuration, no protected paths edited",
        "- secrets gate: no credentials in the diff",
        f"- `{plan.profile}` build, lint and test commands, against the real project",
        "",
        "Opened by [Longhaul](https://github.com/cybiqon-ai/longhaul). "
        "**Auto-merge is off** — this is waiting for you.",
    ]
    return "\n".join(lines)
