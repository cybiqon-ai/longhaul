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


def test_auth_check_fails_without_credentials(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.setattr(doctor, "_which", lambda b: "/usr/bin/claude")
    check = doctor.check_claude_authenticated()
    assert not check.ok
    assert "TOKEN" in check.detail or "KEY" in check.detail
