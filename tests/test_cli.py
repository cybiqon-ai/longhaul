import pytest

from longhaul.cli import build_parser, main


def test_version_flag():
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0


def test_planned_commands_exit_two(capsys):
    assert main(["run"]) == 2
    assert "not implemented yet" in capsys.readouterr().out


def test_every_planned_command_is_registered():
    parser = build_parser()
    actions = [a for a in parser._actions if a.dest == "command"]
    names = set(actions[0].choices)
    assert {"doctor", "gate", "init", "plan", "run", "report", "ui"} <= names


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
