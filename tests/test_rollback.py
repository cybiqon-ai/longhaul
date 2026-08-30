"""Undoing a day.

Destructive by definition, so the default describes and changes nothing.
"""

import subprocess

import pytest

from longhaul.core import gitops, rollback
from longhaul.schema.plan import Plan
from longhaul.schema.state import DONE, PENDING, State

PLAN = {
    "project": "Neon Drift", "target_days": 3, "profile": "flutter-android",
    "milestones": [{"id": "m1", "title": "Core", "tasks": [
        {"id": "t1", "day": 1, "title": "Scaffold", "acceptance_criteria": ["a"]},
        {"id": "t2", "day": 2, "title": "Loop", "acceptance_criteria": ["b"]},
        {"id": "t3", "day": 3, "title": "Levels", "acceptance_criteria": ["c"]},
    ]}],
}


def plan():
    return Plan.from_dict(PLAN)


@pytest.fixture
def repo(tmp_path):
    def git(*args):
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True,
                       capture_output=True)

    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    for task_id, day in (("t1", 1), ("t2", 2), ("t3", 3)):
        (tmp_path / f"{task_id}.txt").write_text(f"day {day}\n")
        git("add", "-A")
        git("commit", "-qm", f"{task_id}")
        git("tag", "-a", gitops.tag_name(task_id), "-m", f"day {day}")
    return tmp_path


def state_with_all_done():
    s = State()
    for t in ("t1", "t2", "t3"):
        s.task(t).status = DONE
        s.task(t).commit_sha = "deadbeef"
        s.task(t).pr_number = 1
    return s


# --- planning it ----------------------------------------------------------

def test_rolling_back_day_2_covers_day_2_and_everything_after():
    assert rollback.tasks_from_day(plan(), 2) == ["t2", "t3"]


def test_rolling_back_day_1_covers_everything():
    assert rollback.tasks_from_day(plan(), 1) == ["t1", "t2", "t3"]


def test_a_day_outside_the_plan_is_refused(repo):
    r = rollback.plan_rollback(plan(), State(), 9, repo)
    assert not r.ok and "outside 1..3" in r.problems[0]


def test_it_targets_the_last_checkpoint_before_that_day(repo):
    r = rollback.plan_rollback(plan(), state_with_all_done(), 3, repo)
    assert r.ok
    assert r.target == gitops.tag_name("t2")
    assert r.tags_removed == [gitops.tag_name("t3")]


def test_rolling_back_day_1_has_nothing_to_return_to(repo):
    """There is no checkpoint before the first day. Say so rather than
    silently discarding the whole repository."""
    r = rollback.plan_rollback(plan(), state_with_all_done(), 1, repo)
    assert not r.ok
    assert "nothing to go back to" in r.problems[0]


# --- doing it -------------------------------------------------------------

def test_planning_alone_changes_nothing(repo):
    before = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                            capture_output=True, text=True).stdout
    rollback.plan_rollback(plan(), state_with_all_done(), 2, repo)
    after = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                           capture_output=True, text=True).stdout
    assert before == after
    assert (repo / "t3.txt").exists()


def test_applying_resets_the_tree_and_removes_the_checkpoints(repo):
    state = state_with_all_done()
    r = rollback.plan_rollback(plan(), state, 2, repo)
    rollback.apply(r, state, repo)

    assert r.applied
    assert (repo / "t1.txt").exists()
    assert not (repo / "t2.txt").exists(), "day 2 onwards should be gone"
    assert not (repo / "t3.txt").exists()
    tags = subprocess.run(["git", "-C", str(repo), "tag", "--list"],
                          capture_output=True, text=True).stdout
    assert gitops.tag_name("t1") in tags
    assert gitops.tag_name("t2") not in tags


def test_applying_returns_the_tasks_to_pending_so_they_run_again(repo):
    state = state_with_all_done()
    r = rollback.plan_rollback(plan(), state, 2, repo)
    rollback.apply(r, state, repo)

    assert state.tasks["t1"].status == DONE, "earlier days are untouched"
    for task_id in ("t2", "t3"):
        ts = state.tasks[task_id]
        assert ts.status == PENDING
        assert ts.attempts == 0
        assert ts.commit_sha is None and ts.pr_number is None
        assert ts.error_fingerprints == []


def test_a_refused_rollback_is_never_applied(repo):
    state = state_with_all_done()
    r = rollback.plan_rollback(plan(), state, 1, repo)
    rollback.apply(r, state, repo)
    assert not r.applied
    assert (repo / "t3.txt").exists()


# --- tags -----------------------------------------------------------------

def test_a_tag_is_not_silently_moved(repo):
    """Re-running a finished day must not move a checkpoint someone may
    already have rolled back to."""
    first = subprocess.run(
        ["git", "-C", str(repo), "rev-list", "-n", "1", gitops.tag_name("t1")],
        capture_output=True, text=True).stdout.strip()
    gitops.tag(repo, "t1", "a different message")
    second = subprocess.run(
        ["git", "-C", str(repo), "rev-list", "-n", "1", gitops.tag_name("t1")],
        capture_output=True, text=True).stdout.strip()
    assert first == second
