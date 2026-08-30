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


@pytest.fixture
def no_bundle(monkeypatch, tmp_path):
    """Force the zero-dependency fallback.

    Both modes have to work: a released wheel ships the exported app, a source
    checkout before `npm run build` does not, and the tool must be usable either
    way. Whichever happens to exist on the machine running the suite cannot
    decide which one gets tested.
    """
    monkeypatch.setattr(server, "STATIC_DIR", tmp_path / "absent")


@pytest.fixture
def bundle(monkeypatch, tmp_path):
    """Force the bundled-app path, with a stand-in export."""
    static = tmp_path / "static"
    (static / "p" / "_").mkdir(parents=True)
    (static / "index.html").write_text("<!doctype html><title>App</title>HOME")
    (static / "p" / "_.html").write_text("<!doctype html>PROJECT")
    (static / "p" / "_" / "tasks.html").write_text("<!doctype html>TASKS")
    (static / "_next").mkdir()
    (static / "_next" / "app.js").write_text("console.log(1)")
    monkeypatch.setattr(server, "STATIC_DIR", static)
    return static

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

def test_the_fallback_page_is_served_when_no_app_is_bundled(no_bundle, live):
    """A source checkout before `npm run build` still gets a working interface."""
    status, body, headers = get(live, "/")
    assert status == 200
    assert body.startswith("<!doctype html>")
    assert "Neon Drift" in body
    assert "EventSource" in body, "the page must be able to update itself"
    assert headers["Content-Type"].startswith("text/html")


def test_the_fallback_page_carries_no_data_because_it_fetches_it(no_bundle, live):
    """The document stays small however long a project runs."""
    _status, body, _ = get(live, "/")
    assert 'id="longhaul-data"' not in body
    assert "/api/data" in body


def test_the_bundled_app_is_served_when_present(bundle, live):
    _status, body, _ = get(live, "/")
    assert "HOME" in body


def test_a_project_route_is_rewritten_onto_the_exported_file(bundle, live):
    """A static export has no file for /p/neon-drift/tasks. Serving index.html
    there would hand back the home page, so the route is rewritten onto the
    prerendered `_` equivalent and the client reads the real id from the URL."""
    assert "TASKS" in get(live, "/p/neon-drift/tasks")[1]
    assert "PROJECT" in get(live, "/p/neon-drift")[1]


def test_an_unknown_route_falls_back_to_the_app_shell(bundle, live):
    assert "HOME" in get(live, "/something/else")[1]


def test_a_missing_asset_is_a_404_not_the_app_shell(bundle, live):
    """Otherwise a broken script tag returns HTML and fails confusingly."""
    with pytest.raises(urllib.error.HTTPError) as exc:
        get(live, "/_next/missing.js")
    assert exc.value.code == 404


def test_the_bundled_app_cannot_serve_files_outside_itself(bundle, live):
    with pytest.raises(urllib.error.HTTPError) as exc:
        get(live, "/_next/../../../etc/passwd")
    assert exc.value.code == 404


@pytest.mark.parametrize("route,expected", [
    ("/p/neon-drift", "/p/_"),
    ("/p/neon-drift/tasks", "/p/_/tasks"),
    ("/p/a-b-c/chats", "/p/_/chats"),
    ("/p/_", "/p/_"),
    ("/p/_/tasks", "/p/_/tasks"),
    ("/", "/"),
    ("/_next/app.js", "/_next/app.js"),
])
def test_the_rewrite_only_touches_project_routes(route, expected):
    assert server._rewrite_project_route(route) == expected


def test_the_data_endpoint_returns_the_whole_payload(live):
    _status, body, headers = get(live, "/api/data")
    assert headers["Content-Type"] == "application/json"
    payload = json.loads(body)
    assert payload["project"] == "Neon Drift"
    assert len(payload["tasks"]) == 2
    assert sum(payload["counts"].values()) == payload["tasks_total"]


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

def test_a_missing_plan_renders_a_message_rather_than_crashing(no_bundle, tmp_path):
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
        _status, body, _ = get(f"http://127.0.0.1:{srv.server_address[1]}", "/api/data")
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


# --- serving proof artefacts ----------------------------------------------

def _put_proof(root, name=b"screenshot.png"):
    path = root / ".longhaul" / "proof" / "day-01" / "t1" / "screenshot.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\nimagebytes")
    return path


def test_a_proof_artefact_is_served_with_its_real_type(project, live):
    _put_proof(project)
    with urllib.request.urlopen(
        live + "/.longhaul/proof/day-01/t1/screenshot.png", timeout=5
    ) as r:
        assert r.status == 200
        assert r.headers["Content-Type"] == "image/png"
        assert r.read() == b"\x89PNG\r\nimagebytes"


@pytest.mark.parametrize("attack", [
    "/.longhaul/proof/../../../etc/passwd",
    "/.longhaul/proof/../state.json",
    "/.longhaul/proof/day-01/../../../../etc/hosts",
    "/.longhaul/proof/%2e%2e/%2e%2e/state.json",
])
def test_the_proof_route_cannot_walk_out_of_the_proof_directory(live, attack):
    """This route reads files off disk by URL, so it has to be proven, not
    assumed. Percent-encoding is decoded before the check, not after."""
    with pytest.raises(urllib.error.HTTPError) as exc:
        get(live, attack)
    assert exc.value.code == 404


def test_a_missing_artefact_is_a_404_not_a_stack_trace(live):
    with pytest.raises(urllib.error.HTTPError) as exc:
        get(live, "/.longhaul/proof/day-99/t9/nope.png")
    assert exc.value.code == 404


def test_the_live_payload_links_artefacts_rather_than_embedding_them(project, live):
    """Served locally the browser fetches them, so the payload stays small
    however long the project runs."""
    _put_proof(project)
    payload = json.loads(get(live, "/api/data")[1])
    shot = payload["proof"][0]
    assert shot["src"] == ".longhaul/proof/day-01/t1/screenshot.png"
    assert not shot["src"].startswith("data:")
