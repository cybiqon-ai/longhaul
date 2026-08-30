"""The live server.

stdlib only, localhost by default, and it must never hand a credential to a
browser — the page renders agent output verbatim.
"""

import json
import threading
import urllib.request

import pytest
import yaml

from longhaul.core import state as state_io
from longhaul.schema.state import DONE, FAILED, State
from longhaul.ui import redact, server

PLAN = {
    "project": "Neon Drift", "target_days": 2, "profile": "flutter-android",
    "milestones": [{"id": "m1", "title": "Core", "tasks": [
        {"id": "t1", "day": 1, "title": "Scaffold", "acceptance_criteria": ["a"]},
        {"id": "t2", "day": 2, "title": "Loop", "acceptance_criteria": ["b"]},
    ]}],
}


@pytest.fixture
def project(tmp_path):
    (tmp_path / ".longhaul").mkdir()
    (tmp_path / ".longhaul" / "plan.yaml").write_text(yaml.safe_dump(PLAN))
    s = State(project="Neon Drift")
    s.task("t1").status = DONE
    s.task("t1").cost_usd = 1.99
    state_io.save(s, tmp_path)
    return tmp_path


@pytest.fixture
def live(project):
    srv = server.serve(project, "127.0.0.1", 0)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.stopping = True
    srv.shutdown()
    srv.server_close()


def get(url, path):
    with urllib.request.urlopen(url + path, timeout=5) as r:
        return r.status, r.read().decode(), dict(r.headers)


# --- routes ---------------------------------------------------------------

def test_the_root_serves_a_whole_page_with_the_live_listener(live):
    status, body, headers = get(live, "/")
    assert status == 200
    assert body.startswith("<!doctype html>")
    assert "Neon Drift" in body
    assert "EventSource" in body, "the page must be able to update itself"
    assert headers["Content-Type"].startswith("text/html")


def test_the_fragment_is_just_the_body_for_swapping_in(live):
    _status, body, _ = get(live, "/fragment")
    assert body.startswith("<main>")
    assert "<!doctype" not in body
    assert "EventSource" not in body, "the fragment must not re-add the listener"


def test_the_api_returns_the_same_numbers_as_the_page(live):
    _status, body, headers = get(live, "/api/summary")
    assert headers["Content-Type"] == "application/json"
    data = json.loads(body)
    assert data["project"] == "Neon Drift"
    assert data["done"] == 1 and data["pending"] == 1
    buckets = ("done", "failed", "parked", "halted", "in_progress", "skipped", "pending")
    assert sum(data[b] for b in buckets) == data["tasks"]


def test_an_unknown_route_is_a_404(live):
    with pytest.raises(urllib.error.HTTPError) as exc:
        get(live, "/../../etc/passwd")
    assert exc.value.code == 404


def test_responses_carry_the_headers_that_stop_embedding(live):
    _status, _body, headers = get(live, "/")
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Cache-Control"] == "no-store"


# --- it works without a plan ----------------------------------------------

def test_a_missing_plan_renders_a_message_rather_than_crashing(tmp_path):
    srv = server.serve(tmp_path, "127.0.0.1", 0)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        _status, body, _ = get(f"http://127.0.0.1:{srv.server_address[1]}", "/")
        assert "no plan at" in body
    finally:
        srv.stopping = True
        srv.shutdown()
        srv.server_close()


# --- change detection -----------------------------------------------------

def test_the_stamp_changes_when_state_changes(project):
    before = server._stamp(project)
    s = state_io.load(project)
    s.task("t2").status = DONE
    state_io.save(s, project)
    assert server._stamp(project) != before


def test_the_stamp_is_stable_when_nothing_changes(project):
    assert server._stamp(project) == server._stamp(project)


def test_a_missing_file_does_not_break_the_stamp(tmp_path):
    assert server._stamp(tmp_path)  # no .longhaul at all


# --- redaction ------------------------------------------------------------

def test_a_token_in_agent_output_never_reaches_the_browser(project):
    """report.html gets committed, attached to issues and screenshotted."""
    token = "ghp_" + "A" * 36
    s = state_io.load(project)
    s.task("t2").status = FAILED
    s.task("t2").last_error = f"fatal: remote rejected, token {token} is invalid"
    state_io.save(s, project)

    srv = server.serve(project, "127.0.0.1", 0)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        _status, body, _ = get(f"http://127.0.0.1:{srv.server_address[1]}", "/")
        assert token not in body
        assert "redacted" in body
    finally:
        srv.stopping = True
        srv.shutdown()
        srv.server_close()


def test_redaction_keeps_the_host_but_drops_the_credential():
    # longhaul: allow-secret — synthetic fixture for the redactor itself
    out = redact.redact("could not push to https://user:hunter2secret@github.com/o/r.git")
    assert "hunter2secret" not in out
    assert "github.com/o/r.git" in out, "the error must stay useful"


def test_redaction_leaves_ordinary_text_alone():
    text = "AssertionError: expected 1, got 2"
    assert redact.redact(text) == text


def test_redaction_handles_nothing():
    assert redact.redact(None) == "" and redact.redact("") == ""


def test_a_port_already_in_use_is_a_message_not_a_traceback(project, capsys):
    """4321 is also Astro's default dev port, so this is normal, not a crash."""
    held = server.serve(project, "127.0.0.1", 0)
    port = held.server_address[1]
    try:
        assert server.run(project, "127.0.0.1", port) == 1
        out = capsys.readouterr().out
        assert "cannot start" in out
        assert "--port" in out, "the message must say how to fix it"
    finally:
        held.server_close()


def test_serve_raises_a_typed_error_rather_than_a_bare_oserror(project):
    held = server.serve(project, "127.0.0.1", 0)
    try:
        with pytest.raises(server.PortInUse):
            server.serve(project, "127.0.0.1", held.server_address[1])
    finally:
        held.server_close()
