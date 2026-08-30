"""The subprocess driver.

Reads `--output-format stream-json`, which carries everything the single-JSON
form did plus the whole conversation — which is what makes a run auditable
after the fact rather than a number in a ledger.
"""

import json

import pytest

from longhaul.driver.base import AgentRequest
from longhaul.driver.cli_driver import ClaudeAuthError, CliDriver


def req(**kw):
    base = {"prompt": "do the thing", "role": "coder", "cwd": "."}
    return AgentRequest(**{**base, **kw})


def stream(*events):
    return "\n".join(json.dumps(e) for e in events) + "\n"


RESULT = {
    "type": "result", "subtype": "success", "is_error": False,
    "result": "done", "session_id": "s1", "total_cost_usd": 0.42,
    "structured_output": {"passes": True},
}


class FakeProc:
    def __init__(self, stdout="", returncode=0, stderr=""):
        self.stdout, self.returncode, self.stderr = stdout, returncode, stderr


# --- argv -----------------------------------------------------------------

def test_argv_never_skips_permissions():
    argv = CliDriver()._argv(req())
    assert "--dangerously-skip-permissions" not in argv
    assert argv[argv.index("--permission-mode") + 1] == "dontAsk"


def test_argv_requests_the_stream_so_a_transcript_exists():
    argv = CliDriver()._argv(req())
    assert argv[argv.index("--output-format") + 1] == "stream-json"
    assert "--verbose" in argv, "stream-json needs it to emit message events"


def test_argv_passes_resume_schema_and_model():
    argv = CliDriver()._argv(req(resume_session="abc-123", model="claude-opus-5",
                                 json_schema={"type": "object"}))
    assert argv[argv.index("--resume") + 1] == "abc-123"
    assert argv[argv.index("--model") + 1] == "claude-opus-5"
    assert json.loads(argv[argv.index("--json-schema") + 1]) == {"type": "object"}


# --- parsing --------------------------------------------------------------

def test_a_non_json_line_does_not_end_the_stream():
    """The CLI interleaves warnings — 'no stdin data received' arrives first."""
    stdout = "Warning: no stdin data received in 3s\n" + stream(RESULT)
    events = CliDriver._events(stdout)
    assert len(events) == 1
    assert CliDriver._result_of(events)["session_id"] == "s1"


def test_the_last_result_event_wins():
    events = CliDriver._events(stream({"type": "assistant"}, RESULT))
    assert CliDriver._result_of(events)["result"] == "done"


def test_no_result_event_is_not_success(monkeypatch):
    """A stream with no result never really started."""
    monkeypatch.setattr(
        CliDriver, "run", CliDriver.run)  # keep the real method
    driver = CliDriver()
    monkeypatch.setattr(
        "longhaul.driver.cli_driver.subprocess.run",
        lambda *a, **k: FakeProc(stream({"type": "assistant"}), 0))
    result = driver.run(req())
    assert not result.ok
    assert "no result event" in result.error


def test_empty_stdout_is_not_success(monkeypatch):
    monkeypatch.setattr(
        "longhaul.driver.cli_driver.subprocess.run", lambda *a, **k: FakeProc("", 0))
    assert not CliDriver().run(req()).ok


def test_a_successful_run_carries_cost_session_and_structured_output(monkeypatch):
    monkeypatch.setattr(
        "longhaul.driver.cli_driver.subprocess.run",
        lambda *a, **k: FakeProc(stream({"type": "system", "subtype": "init"}, RESULT)))
    result = CliDriver().run(req())
    assert result.ok
    assert result.session_id == "s1"
    assert result.cost_usd == 0.42
    assert result.structured == {"passes": True}
    assert result.text == "done"


def test_an_auth_failure_raises_rather_than_returning(monkeypatch):
    bad = {**RESULT, "is_error": True, "subtype": "error", "error": "authentication_failed"}
    monkeypatch.setattr(
        "longhaul.driver.cli_driver.subprocess.run", lambda *a, **k: FakeProc(stream(bad)))
    with pytest.raises(ClaudeAuthError):
        CliDriver().run(req())


def test_retries_are_counted_from_the_stream():
    """A run that succeeded after three 429s cost wall-clock that is otherwise
    invisible, and a run that is retrying is not a run that is stuck."""
    events = CliDriver._events(stream(
        {"type": "system", "subtype": "api_retry", "error": "rate_limit"},
        {"type": "system", "subtype": "api_retry", "error": "overloaded"},
        RESULT))
    assert CliDriver.retries(events) == ["rate_limit", "overloaded"]


# --- transcripts ----------------------------------------------------------

def test_the_transcript_is_written_verbatim(tmp_path, monkeypatch):
    raw = "Warning: something\n" + stream({"type": "assistant"}, RESULT)
    monkeypatch.setattr(
        "longhaul.driver.cli_driver.subprocess.run", lambda *a, **k: FakeProc(raw))
    path = tmp_path / "runs" / "day-01" / "coder.jsonl"
    CliDriver().run(req(transcript_path=str(path)))
    assert path.read_text() == raw, "nothing may be lost to a summariser"


def test_no_transcript_path_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "longhaul.driver.cli_driver.subprocess.run", lambda *a, **k: FakeProc(stream(RESULT)))
    CliDriver().run(req())
    assert list(tmp_path.iterdir()) == []


def test_an_unwritable_transcript_does_not_break_the_run(tmp_path, monkeypatch):
    """A full disk must lose the record of the work, never the work."""
    monkeypatch.setattr(
        "longhaul.driver.cli_driver.subprocess.run", lambda *a, **k: FakeProc(stream(RESULT)))
    blocked = tmp_path / "file"
    blocked.write_text("x")
    result = CliDriver().run(req(transcript_path=str(blocked / "nested" / "t.jsonl")))
    assert result.ok
