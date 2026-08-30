"""Git Ops, and the check most pipelines get silently wrong.

GitHub does not trigger workflows on commits pushed with the default
GITHUB_TOKEN. A pipeline that pushes with it gets green PRs and a CI system that
never ran — no error, no warning. "CI is the source of truth" then means nothing
checked anything, so Longhaul asks every time and treats silence as failure.
"""

import subprocess

import pytest

from longhaul.core import gitops
from longhaul.integrations.github import GitHubError, parse_remote
from longhaul.schema.plan import Plan

PLAN = {
    "project": "Neon Drift", "target_days": 3, "profile": "flutter-android",
    "milestones": [{"id": "m1", "title": "Core", "tasks": [
        {"id": "t1", "day": 1, "kind": "infra", "title": "Scaffold and CI",
         "acceptance_criteria": ["flutter analyze exits 0", "CI ships a debug APK"]},
    ]}],
}


class FakeGitHub:
    """A stand-in that lets a test say 'the push produced no CI run'."""

    def __init__(self, runs=None, workflows=True, run=None, jobs=0):
        self._runs = runs if runs is not None else []
        self._workflows = workflows
        self._run = run or {"status": "completed", "conclusion": "success"}
        self._jobs = jobs
        self.owner, self.repo = "o", "r"

    def runs_for_sha(self, sha):
        return self._runs

    def has_workflows(self):
        return self._workflows

    def get_run(self, run_id):
        return self._run

    def jobs_for_run(self, run_id):
        return [{"name": f"j{i}"} for i in range(self._jobs)]


def plan():
    return Plan.from_dict(PLAN)


@pytest.fixture
def repo(tmp_path):
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    for k, v in (("user.email", "t@t"), ("user.name", "t")):
        subprocess.run(["git", "-C", str(tmp_path), "config", k, v], check=True)
    (tmp_path / "README.md").write_text("hi\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "init"], check=True)
    return tmp_path


# --- the CI-start check ---------------------------------------------------

def test_no_ci_run_with_workflows_present_is_a_failure_not_silence():
    run_id, why = gitops.verify_ci_started(
        FakeGitHub(runs=[], workflows=True), "abc123", grace_s=0, sleep=lambda s: None)
    assert run_id is None
    assert "GITHUB_TOKEN" in why, "the explanation must name the actual cause"


def test_no_workflows_at_all_is_reported_honestly_not_as_a_pass():
    run_id, why = gitops.verify_ci_started(
        FakeGitHub(runs=[], workflows=False), "abc123", grace_s=0, sleep=lambda s: None)
    assert run_id is None
    assert "no workflows" in why


def test_a_started_run_is_reported_with_its_id():
    run_id, why = gitops.verify_ci_started(
        FakeGitHub(runs=[{"id": 4471}]), "abc123", grace_s=0, sleep=lambda s: None)
    assert run_id == 4471 and "4471" in why


def test_waiting_reports_the_number_of_jobs_that_actually_ran():
    """A run can conclude 'success' having executed nothing — that is what an
    unparseable workflow file looks like from the outside."""
    conclusion, jobs = gitops.wait_for_ci(
        FakeGitHub(run={"status": "completed", "conclusion": "success"}, jobs=3),
        4471, sleep=lambda s: None)
    assert conclusion == "success" and jobs == 3


def test_a_run_that_never_completes_times_out_rather_than_hanging():
    conclusion, _ = gitops.wait_for_ci(
        FakeGitHub(run={"status": "in_progress"}), 1, timeout_s=0, sleep=lambda s: None)
    assert conclusion == "timed_out"


# --- commit message -------------------------------------------------------

def test_commit_message_is_conventional_and_carries_the_criteria():
    msg = gitops.commit_message(plan(), plan().task("t1"))
    subject = msg.splitlines()[0]
    assert subject.startswith("chore(t1): ")
    assert len(subject) <= 72
    assert "flutter analyze exits 0" in msg
    assert "Written by Longhaul" in msg


def test_a_very_long_title_is_truncated_not_wrapped():
    p = plan()
    p.task("t1").title = "x" * 200
    assert len(gitops.commit_message(p, p.task("t1")).splitlines()[0]) <= 72


# --- ship -----------------------------------------------------------------

def test_ship_commits_but_does_not_push_when_asked_not_to(repo):
    (repo / "new.txt").write_text("x\n")
    result = gitops.ship(plan(), plan().task("t1"), repo, "main", repo, do_push=False)
    assert result.committed and result.sha
    assert not result.pushed
    assert "not pushed" in result.detail


def test_ship_without_a_remote_commits_and_says_so(repo):
    (repo / "new.txt").write_text("x\n")
    result = gitops.ship(plan(), plan().task("t1"), repo, "main", repo, do_push=True)
    assert result.committed and not result.pushed
    assert "no remote" in result.detail


def test_ship_with_nothing_to_commit_is_not_ok(repo):
    subprocess.run(["git", "-C", str(repo), "checkout", "-qb", "empty"], check=True)
    result = gitops.ship(plan(), plan().task("t1"), repo, "empty", repo, do_push=False)
    assert result.sha  # HEAD exists
    assert result.committed


# --- remote parsing -------------------------------------------------------

@pytest.mark.parametrize("url,expected", [
    ("https://github.com/cybiqon-ai/longhaul.git", ("cybiqon-ai", "longhaul")),
    ("https://github.com/cybiqon-ai/longhaul", ("cybiqon-ai", "longhaul")),
    ("git@github.com:cybiqon-ai/longhaul.git", ("cybiqon-ai", "longhaul")),
])
def test_parses_github_remotes(url, expected):
    assert parse_remote(url) == expected


def test_rejects_a_non_github_remote():
    with pytest.raises(GitHubError):
        parse_remote("https://gitlab.com/a/b.git")


def test_a_token_in_a_remote_url_is_not_echoed_into_the_error():
    """Error strings reach logs, PR bodies and Telegram.

    The first version of this test was `assert "ghp_" not in msg or "example.com"
    in msg` — which passes on the second clause while the token is echoed in
    full. A test with an `or` in its assertion usually asserts nothing.
    """
    token = "ghp_" + "A" * 36
    with pytest.raises(GitHubError) as exc:
        # longhaul: allow-secret — synthetic fixture, assembled above
        parse_remote(f"https://user:{token}@example.com/a/b.git")
    message = str(exc.value)
    assert token not in message
    assert "***:***@" in message
    assert "example.com" in message, "the host must survive so the error is useful"
