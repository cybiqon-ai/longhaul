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
