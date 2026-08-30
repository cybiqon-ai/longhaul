from longhaul.driver.base import AgentRequest
from longhaul.driver.cli_driver import CliDriver


def req(**kw):
    base = {"prompt": "do the thing", "role": "coder", "cwd": "."}
    return AgentRequest(**{**base, **kw})


def test_argv_never_skips_permissions():
    argv = CliDriver()._argv(req())
    assert "--dangerously-skip-permissions" not in argv
    assert argv[argv.index("--permission-mode") + 1] == "dontAsk"


def test_argv_requests_json_and_passes_resume():
    argv = CliDriver()._argv(req(resume_session="abc-123"))
    assert argv[argv.index("--output-format") + 1] == "json"
    assert argv[argv.index("--resume") + 1] == "abc-123"


def test_empty_stdout_is_not_success():
    assert CliDriver._parse("") is None
    assert CliDriver._parse("Login required") is None


def test_parses_a_result_payload():
    payload = CliDriver._parse('{"result":"ok","session_id":"s1","total_cost_usd":0.42}')
    assert payload["session_id"] == "s1"
    assert payload["total_cost_usd"] == 0.42
