from longhaul import doctor


def test_report_counts_and_fails_on_a_fatal_check(capsys):
    checks = [
        doctor.Check("a", True, "fine"),
        doctor.Check("b", False, "broken"),
        doctor.Check("c", False, "missing", fatal=False),
    ]
    code = doctor.report(checks)
    out = capsys.readouterr().out
    assert code == 1
    assert "checks: 3  passed: 1  failed: 1  warnings: 1" in out


def test_a_stored_subscription_login_counts_as_authenticated(monkeypatch):
    """The CLI's own login is the primary path — an env var is not required.

    Requiring one broke `doctor` on a machine where `claude` was perfectly
    logged in, which is the common case this tool is built for.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.setattr(doctor, "_which", lambda b: "/usr/bin/claude")
    monkeypatch.setattr(doctor.subprocess, "run", lambda *a, **k: _Proc(0, "ok"))
    check = doctor.check_claude_authenticated()
    assert check.ok
    assert "stored login" in check.detail


def test_an_expired_session_is_a_failure_with_a_remedy(monkeypatch):
    """Exit 0 with an auth message in the result has cost four nights before."""
    monkeypatch.setattr(doctor, "_which", lambda b: "/usr/bin/claude")
    monkeypatch.setattr(doctor.subprocess, "run",
                        lambda *a, **k: _Proc(0, "OAuth session expired"))
    check = doctor.check_claude_authenticated()
    assert not check.ok
    assert "setup-token" in check.detail


def test_empty_stdout_is_a_failure(monkeypatch):
    monkeypatch.setattr(doctor, "_which", lambda b: "/usr/bin/claude")
    monkeypatch.setattr(doctor.subprocess, "run", lambda *a, **k: _Proc(0, ""))
    assert not doctor.check_claude_authenticated().ok


class _Proc:
    def __init__(self, returncode, stdout):
        self.returncode, self.stdout, self.stderr = returncode, stdout, ""


def test_doctor_does_not_use_bare_mode(monkeypatch):
    """Bare mode ignores OAuth, so it would test a path the driver never takes."""
    seen = {}

    def capture(argv, **kw):
        seen["argv"] = argv
        return _Proc(0, "ok")

    monkeypatch.setattr(doctor, "_which", lambda b: "/usr/bin/claude")
    monkeypatch.setattr(doctor.subprocess, "run", capture)
    doctor.check_claude_authenticated()
    assert "--bare" not in seen["argv"]
