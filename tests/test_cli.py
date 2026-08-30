import pytest

from longhaul.cli import build_parser, main


def test_version_flag():
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0


def test_planned_commands_exit_two(capsys):
    assert main(["ui"]) == 2
    assert "not implemented yet" in capsys.readouterr().out


def test_every_planned_command_is_registered():
    parser = build_parser()
    actions = [a for a in parser._actions if a.dest == "command"]
    names = set(actions[0].choices)
    assert {"doctor", "gate", "init", "plan", "run", "status", "report", "ui"} <= names


def test_gate_command_blocks_a_cheating_diff(tmp_path, capsys):
    diff = tmp_path / "d.diff"
    diff.write_text(
        "--- a/tests/test_x.py\n+++ b/tests/test_x.py\n@@ -1,2 +1,3 @@\n"
        '+@pytest.mark.skip(reason="later")\n def test_x():\n'
    )
    assert main(["gate", "--diff", str(diff)]) == 1
    assert "blocking: 1" in capsys.readouterr().out


def test_gate_fails_on_an_empty_diff(tmp_path, capsys):
    """Exit 0 has already meant 'did nothing' too often to be trusted."""
    empty = tmp_path / "empty.diff"
    empty.write_text("")
    assert main(["gate", "--diff", str(empty)]) == 1
    assert "not a pass" in capsys.readouterr().out


def test_plan_and_simulate_are_real_commands():
    parser = build_parser()
    names = set([a for a in parser._actions if a.dest == "command"][0].choices)
    assert {"plan", "simulate"} <= names


def test_simulate_renders_an_existing_plan_without_calling_the_model(tmp_path, capsys, monkeypatch):
    import yaml

    from longhaul.core import planner
    from longhaul.schema.plan import Plan

    plan = Plan.from_dict({
        "project": "Neon Drift", "target_days": 1, "profile": "flutter-android",
        "milestones": [{"id": "m1", "title": "Core", "tasks": [
            {"id": "t1", "day": 1, "title": "Scaffold",
             "acceptance_criteria": ["CI runs a real test"]}]}],
    })
    f = tmp_path / "plan.yaml"
    f.write_text(yaml.safe_dump(plan.to_dict()))

    def explode(*a, **k):
        raise AssertionError("--from must not invoke the model")
    monkeypatch.setattr(planner, "run", explode)

    assert main(["simulate", "--from", str(f)]) == 0
    out = capsys.readouterr().out
    assert "Neon Drift" in out and "CI runs a real test" in out
    assert "nothing was written" in out


def test_simulate_reports_every_problem_in_a_broken_plan(tmp_path, capsys):
    bad = tmp_path / "plan.yaml"
    bad.write_text("project: ''\ntarget_days: 0\nmilestones: []\n")
    assert main(["simulate", "--from", str(bad)]) == 1
    assert "problems:" in capsys.readouterr().out


def test_plan_refuses_to_clobber_an_existing_plan(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".longhaul").mkdir()
    (tmp_path / ".longhaul" / "plan.yaml").write_text("project: existing\n")
    (tmp_path / "target.md").write_text("# x\n")
    assert main(["plan"]) == 1
    assert "--force" in capsys.readouterr().out


def test_run_refuses_outside_a_git_repository(tmp_path, monkeypatch, capsys):
    """Work happens in worktrees, so there has to be a repo to make one from."""
    monkeypatch.chdir(tmp_path)
    assert main(["run"]) == 1
    assert "not a git repository" in capsys.readouterr().out


def test_run_without_a_plan_says_so(tmp_path, monkeypatch, capsys):
    import subprocess
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc:
        main(["run"])
    assert exc.value.code == 1
    assert "run `longhaul plan` first" in capsys.readouterr().out


def test_status_counts_unstarted_tasks_as_pending(tmp_path, monkeypatch, capsys):
    """A task the plan names but state has never seen is pending, not invisible."""
    import subprocess

    import yaml

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".longhaul").mkdir()
    (tmp_path / ".longhaul" / "plan.yaml").write_text(yaml.safe_dump({
        "project": "p", "target_days": 2, "profile": "flutter-android",
        "milestones": [{"id": "m1", "title": "m", "tasks": [
            {"id": "t1", "day": 1, "title": "a", "acceptance_criteria": ["x"]},
            {"id": "t2", "day": 2, "title": "b", "acceptance_criteria": ["y"]},
        ]}],
    }))
    assert main(["status"]) == 0
    assert "tasks: 2  done: 0  failed: 0  parked: 0  pending: 2" in capsys.readouterr().out


def test_run_accepts_no_push():
    parser = build_parser()
    args = parser.parse_args(["run", "--no-push"])
    assert args.no_push is True
    assert parser.parse_args(["run"]).no_push is False


def test_kill_with_no_run_in_progress_is_not_an_error(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["kill"]) == 0
    assert "no run in progress" in capsys.readouterr().out


def test_kill_cleans_up_a_stale_lock(tmp_path, monkeypatch, capsys):
    """A lock left by a process that died is not a reason to refuse forever."""
    monkeypatch.chdir(tmp_path)
    lock = tmp_path / ".longhaul" / "lock"
    lock.parent.mkdir(parents=True)
    lock.write_text("999999\n")  # a pid that cannot exist
    assert main(["kill"]) == 0
    assert not lock.exists()
    assert "stale" in capsys.readouterr().out


def test_an_overlapping_run_is_skipped_not_failed(tmp_path, monkeypatch, capsys):
    """Two orchestrators sharing one state.json corrupt both, but a skipped
    overlapping cron tick is normal and must not page anyone."""
    import subprocess

    import yaml

    from longhaul.core.lock import acquire

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".longhaul").mkdir(exist_ok=True)
    (tmp_path / ".longhaul" / "plan.yaml").write_text(yaml.safe_dump({
        "project": "p", "target_days": 1, "profile": "flutter-android",
        "milestones": [{"id": "m1", "title": "m", "tasks": [
            {"id": "t1", "day": 1, "title": "a", "acceptance_criteria": ["x"]}]}],
    }))
    with acquire(tmp_path):
        assert main(["run"]) == 0
    assert "another longhaul run" in capsys.readouterr().out


def test_config_template_matches_the_defaults():
    """The template is documentation; if it drifts from the code it misleads."""
    import yaml

    from longhaul.core.init import TEMPLATES
    from longhaul.schema.config import Config

    template = yaml.safe_load((TEMPLATES / "config.yml").read_text())
    defaults = Config()
    assert Config.from_dict(template).limits == defaults.limits, (
        "the template's limits must be the code's defaults, or it misleads"
    )
    assert template["auto_merge"] == defaults.auto_merge
    assert template["limits"]["max_attempts"] == defaults.limits.max_attempts
    assert template["limits"]["identical_failures"] == defaults.limits.identical_failures
    assert template["notify"]["backend"] == defaults.notify.backend


def test_kill_signals_the_whole_group_not_just_the_parent(tmp_path, monkeypatch, capsys):
    """An agent subprocess outlives a SIGTERM'd orchestrator and keeps spending.

    Verified directly: spawn a parent with a child, SIGTERM the parent only, and
    the child survives reparented to init. So the group is the unit of work.
    """
    import os

    from longhaul.core import lock

    monkeypatch.chdir(tmp_path)
    path = tmp_path / ".longhaul" / "lock"
    path.parent.mkdir(parents=True)
    path.write_text("4242\n777\n")

    monkeypatch.setattr(lock, "group_is_alive", lambda pgid: pgid == 777)
    signalled = {}
    monkeypatch.setattr(os, "killpg", lambda pgid, sig: signalled.update(pgid=pgid, sig=sig))
    monkeypatch.setattr(
        os, "kill", lambda *a: pytest.fail("must signal the group, not the pid"))

    assert main(["kill"]) == 0
    assert signalled["pgid"] == 777
    assert "process group 777" in capsys.readouterr().out


def test_kill_only_clears_the_lock_when_the_group_is_empty_too(tmp_path, monkeypatch, capsys):
    """Clearing a lock while an orphan is still working invites a second run
    to collide with it."""
    import os

    from longhaul.core import lock

    monkeypatch.chdir(tmp_path)
    path = tmp_path / ".longhaul" / "lock"
    path.parent.mkdir(parents=True)
    path.write_text("999999\n888\n")  # pid cannot exist, group still alive

    monkeypatch.setattr(lock, "group_is_alive", lambda pgid: True)
    monkeypatch.setattr(os, "killpg", lambda pgid, sig: None)

    assert main(["kill"]) == 0
    assert path.exists(), "the lock must survive while the group is still alive"
