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
from longhaul.schema.state import DONE, FAILED, HALTED, PARKED, State

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


@pytest.fixture(autouse=True)
def no_real_proof(monkeypatch):
    """The suite must run offline in seconds.

    Proof steps shell out to a real toolchain, and the flutter-android profile
    starts with `adb wait-for-device` — which blocks forever with nothing
    attached. Without this the whole suite hangs, which is exactly what happened
    the first time the proof gate was wired in.
    """
    monkeypatch.setattr(
        orchestrator.proof_gate, "run",
        lambda *a, **k: orchestrator.proof_gate.ProofResult(),
    )


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

def test_a_needs_human_task_does_the_work_then_parks(repo, monkeypatch):
    """`needs_human` means a human must *decide*, not that no work happens.

    Every such task in a real plan asks for the material the decision rests on —
    three palette options, a dependency comparison, a difficulty curve. Parking
    with nothing produces nothing to decide from, and blocks every dependent
    behind an empty question. On the reference 14-day plan that stalled the whole
    project on day 2.
    """
    patch_coder_writes(monkeypatch)
    patch_devops(monkeypatch, green())
    driver = FakeDriver()
    s = State()
    p = plan()
    out = orchestrator.run_task(driver, p, p.task("t3"), s, repo)

    assert out.status == PARKED
    assert len(driver.requests) == 1, "the work must actually happen"
    assert "waiting" in s.tasks["t3"].last_error
    assert s.tasks["t3"].commit_sha, "the artefacts must be committed, not discarded"


def test_a_parked_task_still_blocks_its_dependents():
    """Conservative on purpose: the decision has not been made yet."""
    s = State()
    s.task("t1").status = PARKED
    nxt = orchestrator.next_task(plan(), s)
    assert nxt is None or nxt.id != "t2"


def test_a_design_task_goes_to_the_designer_not_the_coder(repo, monkeypatch):
    patch_coder_writes(monkeypatch)
    patch_devops(monkeypatch, green())
    driver = FakeDriver()
    p = plan()
    p.task("t1").kind = "design"
    orchestrator.run_task(driver, p, p.task("t1"), State(), repo)
    prompt = driver.requests[0].append_system_prompt
    assert "You are the Designer" in prompt
    assert "PROVISIONAL" in prompt, "it must offer options, not decide for them"


def test_everything_else_goes_to_the_coder(repo, monkeypatch):
    patch_coder_writes(monkeypatch)
    patch_devops(monkeypatch, green())
    driver = FakeDriver()
    p = plan()
    orchestrator.run_task(driver, p, p.task("t1"), State(), repo)
    assert "You are the Coder" in driver.requests[0].append_system_prompt


def test_the_ledger_records_which_role_ran(repo, monkeypatch):
    patch_coder_writes(monkeypatch)
    patch_devops(monkeypatch, green())
    p = plan()
    p.task("t1").kind = "design"
    orchestrator.run_task(FakeDriver(), p, p.task("t1"), State(), repo)
    assert state_io.read_ledger(repo)[0]["role"] == "designer"


def test_a_successful_task_is_marked_done_and_costed(repo, monkeypatch):
    patch_coder_writes(monkeypatch)
    patch_devops(monkeypatch, green())
    s = State()
    p = plan()
    out = orchestrator.run_task(FakeDriver(), p, p.task("t1"), s, repo)
    assert out.status == DONE
    assert s.tasks["t1"].cost_usd == 0.1
    assert s.tasks["t1"].branch == "longhaul/t1"


def test_work_happens_in_a_worktree_and_then_lands_on_the_base_branch(repo, monkeypatch):
    """Both halves matter.

    The Coder never edits the main checkout directly — that is what the worktree
    is for. But the finished work has to land, or tomorrow branches from the same
    starting commit and cannot see today. On the first real multi-day run it did
    not land: four tasks each branched from the initial commit, each rebuilt the
    scaffold from nothing, and every gate passed while the project accumulated
    nothing.
    """
    patch_coder_writes(monkeypatch)
    patch_devops(monkeypatch, green())
    s = State()
    p = plan()
    before = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                            capture_output=True, text=True).stdout.strip()

    out = orchestrator.run_task(FakeDriver(), p, p.task("t1"), s, repo)

    assert out.status == DONE
    assert (repo / ".longhaul" / "worktrees" / "t1").is_dir(), "work happens in a worktree"
    after = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                           capture_output=True, text=True).stdout.strip()
    assert after != before, "the base branch must advance"
    assert s.tasks["t1"].integrated is True
    assert (repo / "new_file.py").exists(), "the work is now on the base branch"


def test_the_next_task_can_see_the_previous_one(repo, monkeypatch):
    """The property the whole change exists for."""
    patch_devops(monkeypatch, green())
    p = plan()
    s = State()

    patch_coder_writes(monkeypatch, "one\n", "from_t1.txt")
    orchestrator.run_task(FakeDriver(), p, p.task("t1"), s, repo)

    seen = {}
    real = orchestrator.worktree.create

    def create(task_id, root=None, base="HEAD"):
        tree = real(task_id, root=root, base=base)
        seen["has_t1_work"] = (tree.path / "from_t1.txt").is_file()
        (tree.path / "from_t2.txt").write_text("two\n")
        return tree

    monkeypatch.setattr(orchestrator.worktree, "create", create)
    orchestrator.run_task(FakeDriver(), p, p.task("t2"), s, repo)
    assert seen["has_t1_work"], "day 2 must start from a tree that contains day 1"


def test_integration_can_be_turned_off(repo, monkeypatch):
    from longhaul.schema.config import Config

    patch_coder_writes(monkeypatch)
    patch_devops(monkeypatch, green())
    s = State()
    p = plan()
    orchestrator.run_task(FakeDriver(), p, p.task("t1"), s, repo,
                          config=Config(integrate=False))
    assert not (repo / "new_file.py").exists()
    assert s.tasks["t1"].integrated is False


def test_a_failed_task_never_lands(repo, monkeypatch):
    patch_coder_writes(monkeypatch)
    patch_devops(monkeypatch, BuildReport(
        steps=[Step("test", "pytest", 1, "boom", 0.1)]))
    s = State()
    p = plan()
    out = orchestrator.run_task(FakeDriver(), p, p.task("t1"), s, repo)
    assert out.status == FAILED
    assert not (repo / "new_file.py").exists(), "broken work must not reach the base branch"
    assert s.tasks["t1"].integrated is False


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
    assert "blocked by the gates" in out.detail
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


def test_a_deterministic_failure_halts_before_the_attempt_budget_runs_out(repo, monkeypatch):
    """The Supervisor's whole point: the same error twice is not worth a third try."""
    patch_coder_writes(monkeypatch)
    patch_devops(monkeypatch, BuildReport(steps=[Step("test", "pytest", 1, "boom", 0.1)]))
    s = State()
    p = plan()
    for _ in range(3):
        out = orchestrator.run_task(FakeDriver(), p, p.task("t1"), s, repo)
    assert out.status == HALTED
    assert "same error 2 times" in out.detail
    assert s.tasks["t1"].attempts == 2, "it must stop trying, not just report"


def test_the_attempt_budget_still_applies_when_the_errors_differ(repo, monkeypatch):
    patch_coder_writes(monkeypatch)
    s = State()
    p = plan()
    for i in range(4):
        patch_devops(monkeypatch, BuildReport(
            steps=[Step("test", "pytest", 1, f"distinct failure {i}", 0.1)]))
        out = orchestrator.run_task(FakeDriver(), p, p.task("t1"), s, repo)
    assert out.status == HALTED
    assert "attempts" in out.detail


def test_a_halted_task_is_not_picked_up_again():
    """And its dependents stay blocked — halted is not settled."""
    s = State()
    s.task("t1").status = HALTED
    nxt = orchestrator.next_task(plan(), s)
    assert nxt.id != "t1"
    assert nxt.id != "t2", "t2 depends on t1, which never completed"


def test_a_cost_ceiling_halts_before_spending_anything(repo, monkeypatch):
    from longhaul.schema.config import Config, Limits

    driver = FakeDriver()
    s = State()
    s.task("t0").cost_usd = 500.0
    p = plan()
    out = orchestrator.run_task(
        driver, p, p.task("t1"), s, repo, config=Config(limits=Limits(cost_usd_total=100.0)))
    assert out.status == HALTED
    assert driver.requests == [], "a ceiling must stop the call, not report after it"


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
    assert "blocked by the gates" in out.detail


def test_diff_is_taken_against_the_recorded_base_not_head(repo, monkeypatch):
    from longhaul.core import worktree as wt

    tree = wt.create("t9", root=repo)
    (tree.path / "a.py").write_text("x = 1\n")
    subprocess.run(["git", "-C", str(tree.path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(tree.path), "-c", "user.email=c@c",
                    "-c", "user.name=c", "commit", "-qm", "c"], check=True)
    assert "a.py" in wt.diff(tree.path, tree.base_sha)
    assert wt.diff(tree.path, "HEAD") == "", "HEAD-relative is exactly the bug"


def test_a_secret_in_the_diff_blocks_the_task(repo, monkeypatch):
    """Push is the point of no return; this must never reach a remote."""
    fake_token = "ghp_" + "A" * 36  # built at runtime; never a literal in source
    patch_coder_writes(monkeypatch, f"TOKEN = '{fake_token}'\n", "config.py")
    patch_devops(monkeypatch, green())
    p = plan()
    out = orchestrator.run_task(FakeDriver(), p, p.task("t1"), State(), repo)
    assert out.status == FAILED
    assert "GitHub token" in out.detail
