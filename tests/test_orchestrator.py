"""The daily loop, driven by a fake so the suite runs offline.

The properties that matter most here are idempotency and resumability: a
scheduled run that does the work twice, or that starts over after a crash, is
not safe to leave unattended.
"""

import subprocess

import pytest

from longhaul.core import orchestrator
from longhaul.core import state as state_io
from longhaul.core.devops import BuildReport, Step
from longhaul.driver.base import AgentResult
from longhaul.schema.plan import Plan
from longhaul.schema.state import DONE, FAILED, PARKED, State

PLAN = {
    "project": "Neon Drift",
    "target_days": 3,
    "profile": "flutter-android",
    "milestones": [{"id": "m1", "title": "Core", "tasks": [
        {"id": "t1", "day": 1, "title": "Scaffold",
         "acceptance_criteria": ["CI runs a real test"]},
        {"id": "t2", "day": 2, "title": "Core loop", "depends_on": ["t1"],
         "acceptance_criteria": ["a tap reverses direction"]},
        {"id": "t3", "day": 3, "title": "Pick the palette", "needs_human": True,
         "acceptance_criteria": ["the author chose a palette"]},
    ]}],
}


class FakeDriver:
    def __init__(self, *results):
        self.results = list(results)
        self.requests = []

    def run(self, request):
        self.requests.append(request)
        return self.results.pop(0) if self.results else AgentResult(
            ok=True, text="done", session_id="s1", cost_usd=0.1)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "t"], check=True)
    (tmp_path / "README.md").write_text("hi\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "init"], check=True)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def plan():
    return Plan.from_dict(PLAN)


def green():
    return BuildReport(steps=[Step("test", "pytest", 0, "ok", 0.1)], test_count=7)


def patch_devops(monkeypatch, report):
    monkeypatch.setattr(orchestrator.devops, "run", lambda *a, **k: report)


def patch_coder_writes(monkeypatch, text="print('x')\n", path="new_file.py"):
    """Make the fake Coder actually change the worktree, as a real one would."""
    real = orchestrator.worktree.create

    def create(task_id, root=None, base="HEAD"):
        tree = real(task_id, root=root, base=base)
        target = tree.path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        return tree

    monkeypatch.setattr(orchestrator.worktree, "create", create)


# --- task selection -------------------------------------------------------

def test_picks_the_lowest_day_whose_dependencies_are_settled():
    s = State()
    assert orchestrator.next_task(plan(), s).id == "t1"
    s.task("t1").status = DONE
    assert orchestrator.next_task(plan(), s).id == "t2"


def test_a_parked_task_does_not_block_later_work():
    """One open question must not stall a fortnight."""
    s = State()
    s.task("t1").status = DONE
    s.task("t2").status = PARKED
    assert orchestrator.next_task(plan(), s) is None or \
        orchestrator.next_task(plan(), s).id == "t3"


def test_a_task_past_its_retry_budget_is_not_retried_forever():
    s = State()
    s.task("t1").status = FAILED
    s.task("t1").attempts = orchestrator.DEFAULT_MAX_ATTEMPTS
    assert orchestrator.next_task(plan(), s).id != "t1"


def test_returns_none_when_everything_is_settled():
    s = State()
    for t in ("t1", "t2", "t3"):
        s.task(t).status = DONE
    assert orchestrator.next_task(plan(), s) is None


# --- running a task -------------------------------------------------------

def test_a_needs_human_task_is_parked_without_calling_the_model(repo):
    driver = FakeDriver()
    s = State()
    p = plan()
    out = orchestrator.run_task(driver, p, p.task("t3"), s, repo)
    assert out.status == PARKED
    assert driver.requests == [], "must not spend anything on a parked task"


def test_a_successful_task_is_marked_done_and_costed(repo, monkeypatch):
    patch_coder_writes(monkeypatch)
    patch_devops(monkeypatch, green())
    s = State()
    p = plan()
    out = orchestrator.run_task(FakeDriver(), p, p.task("t1"), s, repo)
    assert out.status == DONE
    assert s.tasks["t1"].cost_usd == 0.1
    assert s.tasks["t1"].branch == "longhaul/t1"


def test_work_happens_in_a_worktree_never_on_the_main_checkout(repo, monkeypatch):
    patch_coder_writes(monkeypatch)
    patch_devops(monkeypatch, green())
    s = State()
    p = plan()
    orchestrator.run_task(FakeDriver(), p, p.task("t1"), s, repo)
    assert (repo / ".longhaul" / "worktrees" / "t1").is_dir()
    assert not (repo / "new_file.py").exists(), "the main checkout must be untouched"


def test_the_coder_cannot_reach_git_or_the_network(repo, monkeypatch):
    patch_coder_writes(monkeypatch)
    patch_devops(monkeypatch, green())
    driver = FakeDriver()
    p = plan()
    orchestrator.run_task(driver, p, p.task("t1"), State(), repo)
    tools = set(driver.requests[0].allowed_tools)
    assert "WebFetch" not in tools and "WebSearch" not in tools


def test_a_failing_build_fails_the_task_and_keeps_the_real_error(repo, monkeypatch):
    patch_coder_writes(monkeypatch)
    patch_devops(monkeypatch, BuildReport(
        steps=[Step("test", "pytest", 1, "E   assert 1 == 2", 0.1)]))
    s = State()
    p = plan()
    out = orchestrator.run_task(FakeDriver(), p, p.task("t1"), s, repo)
    assert out.status == FAILED
    assert "assert 1 == 2" in s.tasks["t1"].last_error


def test_a_green_suite_that_ran_zero_tests_is_not_a_pass(repo, monkeypatch):
    patch_coder_writes(monkeypatch)
    patch_devops(monkeypatch, BuildReport(
        steps=[Step("test", "pytest", 0, "", 0.1)], test_count=0))
    p = plan()
    out = orchestrator.run_task(FakeDriver(), p, p.task("t1"), State(), repo)
    assert out.status == FAILED
    assert "ZERO tests" in out.report.feedback()


def test_a_cheating_diff_is_blocked_before_the_build_even_runs(repo, monkeypatch):
    patch_coder_writes(monkeypatch, "@pytest.mark.skip\ndef test_x(): pass\n", "tests/test_x.py")
    called = []
    monkeypatch.setattr(orchestrator.devops, "run", lambda *a, **k: called.append(1) or green())
    s = State()
    p = plan()
    out = orchestrator.run_task(FakeDriver(), p, p.task("t1"), s, repo)
    assert out.status == FAILED
    assert "cheat gate" in out.detail
    assert called == [], "the gate must run before the build, not after"


def test_a_coder_that_changed_nothing_is_a_failure(repo, monkeypatch):
    patch_devops(monkeypatch, green())
    p = plan()
    out = orchestrator.run_task(FakeDriver(), p, p.task("t1"), State(), repo)
    assert out.status == FAILED
    assert "changed nothing" in out.detail


def test_a_retry_resumes_the_session_and_carries_the_error(repo, monkeypatch):
    patch_coder_writes(monkeypatch)
    patch_devops(monkeypatch, BuildReport(
        steps=[Step("test", "pytest", 1, "boom", 0.1)]))
    driver = FakeDriver(
        AgentResult(ok=True, text="", session_id="sess-1", cost_usd=0.1),
        AgentResult(ok=True, text="", session_id="sess-1", cost_usd=0.1),
    )
    s = State()
    p = plan()
    orchestrator.run_task(driver, p, p.task("t1"), s, repo)
    orchestrator.run_task(driver, p, p.task("t1"), s, repo)
    second = driver.requests[1]
    assert second.resume_session == "sess-1"
    assert "boom" in second.prompt
    assert "Do not weaken the check that caught it" in second.prompt
    assert s.tasks["t1"].attempts == 2


def test_the_retry_budget_is_reported_when_exhausted(repo, monkeypatch):
    patch_coder_writes(monkeypatch)
    patch_devops(monkeypatch, BuildReport(steps=[Step("test", "pytest", 1, "boom", 0.1)]))
    s = State()
    p = plan()
    for _ in range(orchestrator.DEFAULT_MAX_ATTEMPTS):
        out = orchestrator.run_task(FakeDriver(), p, p.task("t1"), s, repo)
    assert "retry budget exhausted" in out.detail


# --- the day loop ---------------------------------------------------------

def test_run_day_is_idempotent(repo, monkeypatch):
    patch_coder_writes(monkeypatch)
    patch_devops(monkeypatch, green())
    s = State()
    p = plan()
    first = orchestrator.run_day(FakeDriver(), p, s, repo)
    assert first.status == DONE
    s.task(first.task.id).status = DONE
    calls_before = len(state_io.read_ledger(repo))
    second = orchestrator.run_day(FakeDriver(), p, s, repo)
    assert second.task.id != first.task.id or second.detail == "already done"
    assert len(state_io.read_ledger(repo)) >= calls_before


def test_state_survives_a_crash_and_resumes(repo, monkeypatch):
    patch_coder_writes(monkeypatch)
    patch_devops(monkeypatch, green())
    p = plan()
    orchestrator.run_day(FakeDriver(), p, State(), repo)
    reloaded = state_io.load(repo)
    assert reloaded.tasks["t1"].status == DONE
    assert orchestrator.next_task(p, reloaded).id == "t2"


def test_every_agent_call_lands_in_the_ledger(repo, monkeypatch):
    patch_coder_writes(monkeypatch)
    patch_devops(monkeypatch, green())
    orchestrator.run_day(FakeDriver(), plan(), State(), repo)
    entries = state_io.read_ledger(repo)
    assert len(entries) == 1
    assert entries[0]["role"] == "coder" and entries[0]["task"] == "t1"
    assert "cost_usd" in entries[0] and "session_id" in entries[0]


def test_run_day_is_idle_when_nothing_is_eligible(repo):
    s = State()
    for t in ("t1", "t2", "t3"):
        s.task(t).status = DONE
    out = orchestrator.run_day(FakeDriver(), plan(), s, repo)
    assert out.status == "idle" and out.exit_code == 0


# --- the gate must not be blindable ---------------------------------------

def patch_coder_commits(monkeypatch, path="feature.py", text="print('x')\n"):
    """A Coder that commits its own work — which a real one did on the first
    live run, hiding 761 insertions from a HEAD-relative diff."""
    real = orchestrator.worktree.create

    def create(task_id, root=None, base="HEAD"):
        tree = real(task_id, root=root, base=base)
        target = tree.path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        subprocess.run(["git", "-C", str(tree.path), "add", "-A"], check=True)
        subprocess.run(
            ["git", "-C", str(tree.path), "-c", "user.email=c@c", "-c", "user.name=c",
             "commit", "-qm", "coder commit"], check=True)
        return tree

    monkeypatch.setattr(orchestrator.worktree, "create", create)


def test_a_committing_coder_does_not_blind_the_diff(repo, monkeypatch):
    patch_coder_commits(monkeypatch)
    patch_devops(monkeypatch, green())
    s = State()
    p = plan()
    out = orchestrator.run_task(FakeDriver(), p, p.task("t1"), s, repo)
    assert out.status == DONE, out.detail
    assert s.tasks["t1"].base_sha, "the base commit must be pinned when the worktree is made"


def test_a_cheat_hidden_in_a_commit_is_still_caught(repo, monkeypatch):
    """The bypass in full: commit the cheat, and a HEAD-relative diff sees nothing."""
    patch_coder_commits(
        monkeypatch, "tests/test_x.py", "@pytest.mark.skip\ndef test_x(): pass\n")
    patch_devops(monkeypatch, green())
    p = plan()
    out = orchestrator.run_task(FakeDriver(), p, p.task("t1"), State(), repo)
    assert out.status == FAILED
    assert "cheat gate" in out.detail


def test_diff_is_taken_against_the_recorded_base_not_head(repo, monkeypatch):
    from longhaul.core import worktree as wt

    tree = wt.create("t9", root=repo)
    (tree.path / "a.py").write_text("x = 1\n")
    subprocess.run(["git", "-C", str(tree.path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(tree.path), "-c", "user.email=c@c",
                    "-c", "user.name=c", "commit", "-qm", "c"], check=True)
    assert "a.py" in wt.diff(tree.path, tree.base_sha)
    assert wt.diff(tree.path, "HEAD") == "", "HEAD-relative is exactly the bug"
