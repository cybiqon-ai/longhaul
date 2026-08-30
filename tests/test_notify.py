"""The notifier, and the two rules it exists to enforce.

Alerting must not be able to crash the thing it reports on, and a confirmed
message id is the only evidence a notification landed.
"""

import json
import urllib.error

import pytest

from longhaul.core import notify
from longhaul.integrations import telegram
from longhaul.schema.config import Config, Notify
from longhaul.schema.plan import Plan
from longhaul.schema.state import DONE, HALTED, PARKED, State

PLAN = {
    "project": "Neon Drift", "target_days": 14, "profile": "flutter-android",
    "milestones": [{"id": "m1", "title": "Core", "tasks": [
        {"id": "t1", "day": 1, "title": "Scaffold", "acceptance_criteria": ["x"]},
        {"id": "t2", "day": 2, "title": "Loop", "acceptance_criteria": ["y"]},
    ]}],
}


def plan():
    return Plan.from_dict(PLAN)


class FakeResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode()

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def creds(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "1:abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100")


# --- never raises ---------------------------------------------------------

def test_a_network_failure_is_returned_not_raised(monkeypatch, creds):
    """Alerting must not be able to crash the thing it is reporting on."""
    def boom(*a, **k):
        raise urllib.error.URLError("no route to host")

    monkeypatch.setattr(telegram.urllib.request, "urlopen", boom)
    result = telegram.send("hi")
    assert not result.ok and "URLError" in result.error


def test_malformed_json_is_returned_not_raised(monkeypatch, creds):
    class Garbage:
        def read(self):
            return b"<html>502</html>"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(telegram.urllib.request, "urlopen", lambda *a, **k: Garbage())
    assert not telegram.send("hi").ok


def test_missing_credentials_is_reported_not_raised(monkeypatch):
    monkeypatch.delenv("TELEGRAM_TOKEN", raising=False)
    monkeypatch.delenv("LONGHAUL_TELEGRAM_TOKEN", raising=False)
    result = telegram.send("hi")
    assert not result.ok and "TELEGRAM_TOKEN" in result.error


# --- a message id is the only evidence ------------------------------------

def test_http_200_with_ok_false_is_a_failure(monkeypatch, creds):
    """The failure mode that reads as success from the caller's side."""
    monkeypatch.setattr(
        telegram.urllib.request, "urlopen",
        lambda *a, **k: FakeResponse({"ok": False, "description": "chat not found"}))
    result = telegram.send("hi")
    assert not result.ok and "chat not found" in result.error


def test_ok_true_without_a_message_id_is_a_failure(monkeypatch, creds):
    monkeypatch.setattr(
        telegram.urllib.request, "urlopen", lambda *a, **k: FakeResponse({"ok": True}))
    result = telegram.send("hi")
    assert not result.ok and "confirmed nothing" in result.error


def test_a_confirmed_message_id_is_success(monkeypatch, creds):
    monkeypatch.setattr(
        telegram.urllib.request, "urlopen",
        lambda *a, **k: FakeResponse({"ok": True, "result": {"message_id": 4471}}))
    result = telegram.send("hi")
    assert result.ok and result.message_id == 4471


# --- message shaping ------------------------------------------------------

def test_truncates_on_a_line_break_not_mid_word():
    text = "\n".join(f"line {i}" * 20 for i in range(400))
    out = telegram.truncate(text)
    assert len(out) <= telegram.MSG_LIMIT
    assert out.endswith("…")


def test_escapes_html_so_a_stack_trace_cannot_break_the_message():
    assert telegram.escape("<b>&") == "&lt;b&gt;&amp;"


# --- the digest reports counts --------------------------------------------

def test_the_digest_reports_counts_not_a_status():
    s = State()
    s.task("t1").status = DONE
    body = notify.digest(plan(), s, "day 1 finished")
    assert "1 done" in body and "0 failed" in body and "1 to go" in body
    assert "$0.00" in body


def test_the_digest_surfaces_what_needs_a_human():
    s = State()
    s.task("t1").status = PARKED
    s.task("t1").last_error = "the plan reserved this decision for a human"
    s.task("t2").status = HALTED
    s.task("t2").last_error = "daily ceiling reached"
    body = notify.digest(plan(), s, "day 1")
    assert "needs you" in body
    assert "reserved this decision" in body and "daily ceiling" in body


def test_the_digest_links_open_prs():
    s = State()
    s.task("t1").pr_number, s.task("t1").pr_url = 12, "https://github.com/o/r/pull/12"
    assert "#12" in notify.digest(plan(), s, "day 1")


# --- routing --------------------------------------------------------------

def test_no_backend_means_nothing_is_attempted():
    d = notify.send(Config(), plan(), State(), "day 1", failure=False)
    assert not d.attempted and "no notifier" in d.detail


def test_success_notifications_can_be_turned_off():
    cfg = Config(notify=Notify(backend="telegram", on_success=False))
    assert not notify.send(cfg, plan(), State(), "day 1", failure=False).attempted


def test_failures_are_sent_even_when_success_notifications_are_off(monkeypatch, creds):
    monkeypatch.setattr(
        telegram.urllib.request, "urlopen",
        lambda *a, **k: FakeResponse({"ok": True, "result": {"message_id": 7}}))
    cfg = Config(notify=Notify(backend="telegram", on_success=False))
    d = notify.send(cfg, plan(), State(), "it broke", failure=True)
    assert d.attempted and d.ok


def test_an_unknown_backend_is_reported_rather_than_silently_ignored():
    cfg = Config(notify=Notify(backend="carrier-pigeon"))
    d = notify.send(cfg, plan(), State(), "day 1", failure=False)
    assert not d.attempted and "carrier-pigeon" in d.detail
