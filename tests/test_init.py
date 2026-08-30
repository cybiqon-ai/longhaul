"""`longhaul init`, which is where an unattended tool earns or loses trust.

The failure it avoids: discovering on day 4 that the toolchain was never
installed, after four days of work already exist on a branch.
"""

import subprocess

import pytest
import yaml

from longhaul.core import init


@pytest.fixture
def repo(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return tmp_path


def run(root, **kw):
    kw.setdefault("profile", "flutter-android")
    kw.setdefault("target", root / "target.md")
    return init.run(root, **kw)


def test_refuses_outside_a_git_repository(tmp_path):
    result = run(tmp_path, is_repo=False)
    assert not result.ok
    assert "git init" in result.problems[0]


def test_refuses_an_unknown_profile_before_writing_anything(repo):
    result = run(repo, profile="cobol-mainframe")
    assert not result.ok
    assert not (repo / ".longhaul").exists(), "must not half-configure a project"


def test_writes_a_config_a_target_and_a_gitignore(repo):
    result = run(repo)
    assert result.ok
    assert (repo / ".longhaul" / "config.yml").is_file()
    assert (repo / "target.md").is_file()
    assert ".longhaul/worktrees/" in (repo / ".gitignore").read_text()


def test_the_config_carries_the_chosen_profile(repo):
    run(repo, profile="flutter-android")
    written = yaml.safe_load((repo / ".longhaul" / "config.yml").read_text())
    assert written["profile"] == "flutter-android"
    assert written["auto_merge"] is False


def test_never_overwrites_an_existing_file(repo):
    (repo / "target.md").write_text("# my real target\n")
    (repo / ".longhaul").mkdir()
    (repo / ".longhaul" / "config.yml").write_text("profile: mine\n")
    result = run(repo)
    assert (repo / "target.md").read_text() == "# my real target\n"
    assert (repo / ".longhaul" / "config.yml").read_text() == "profile: mine\n"
    assert len(result.skipped) >= 2


def test_is_idempotent(repo):
    run(repo)
    before = (repo / ".gitignore").read_text()
    second = run(repo)
    assert (repo / ".gitignore").read_text() == before, "must not append twice"
    assert second.ok


def test_gitignore_excludes_only_the_generated_parts(repo):
    """plan.yaml, state.json and the ledger are the audit trail — they belong
    in the repository."""
    run(repo)
    body = (repo / ".gitignore").read_text()
    assert ".longhaul/worktrees/" in body
    assert ".longhaul/runs/" in body
    assert ".longhaul/plan.yaml" not in body
    assert ".longhaul/state.json" not in body


@pytest.mark.parametrize("kind,path", [
    ("cron", ".longhaul/cron.txt"),
    ("systemd", ".longhaul/longhaul.timer"),
    ("actions", ".github/workflows/longhaul.yml"),
])
def test_writes_the_requested_schedule(repo, kind, path):
    result = run(repo, schedule=kind)
    assert result.ok
    assert (repo / path).is_file()


def test_the_schedule_files_carry_the_real_project_directory(repo):
    run(repo, schedule="cron")
    assert str(repo) in (repo / ".longhaul" / "cron.txt").read_text()


def test_an_unknown_schedule_is_a_problem_not_a_silent_skip(repo):
    result = run(repo, schedule="carrier-pigeon")
    assert not result.ok


def test_no_schedule_is_written_by_default(repo):
    run(repo)
    assert not (repo / ".longhaul" / "cron.txt").exists()
    assert not (repo / ".github").exists()


def test_the_actions_template_is_valid_yaml_and_serialises_runs(repo):
    """An unparseable workflow fails a run with zero jobs and no logs — which
    has already happened once in this project."""
    run(repo, schedule="actions")
    spec = yaml.safe_load((repo / ".github" / "workflows" / "longhaul.yml").read_text())
    assert spec["jobs"]["run"]["timeout-minutes"] == 120
    assert spec["concurrency"]["group"] == "longhaul"
    assert spec["concurrency"]["cancel-in-progress"] is False


def test_the_cron_line_has_flock_and_a_timeout(repo):
    """House rule: every scheduled entrypoint gets both, and logs to a
    directory that already exists."""
    run(repo, schedule="cron")
    line = [
        ln for ln in (repo / ".longhaul" / "cron.txt").read_text().splitlines()
        if ln.strip() and not ln.startswith("#")
    ][0]
    assert "flock" in line and "timeout" in line and "mkdir -p" in line
