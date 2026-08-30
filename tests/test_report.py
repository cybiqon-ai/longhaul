"""The report: one self-contained file that is fully interactive with no network.

Rendering happens in the browser from an embedded JSON payload, so these test
the payload and the document that carries it, rather than markup a renderer
happens to emit today.
"""

import json
import re

import pytest

from longhaul.schema.plan import Plan
from longhaul.schema.state import DONE, FAILED, HALTED, PARKED, State
from longhaul.ui import data as ui_data
from longhaul.ui import render

PLAN = {
    "project": "Neon Drift", "target_days": 3, "profile": "flutter-android",
    "milestones": [{"id": "m1", "title": "Core loop", "tasks": [
        {"id": "t1", "day": 1, "title": "Scaffold", "kind": "infra",
         "acceptance_criteria": ["flutter analyze exits 0"]},
        {"id": "t2", "day": 2, "title": "Core loop", "depends_on": ["t1"],
         "acceptance_criteria": ["a tap reverses direction"]},
        {"id": "t3", "day": 3, "title": "Pick the palette", "needs_human": True,
         "kind": "design", "acceptance_criteria": ["the author chose one"]},
    ]}],
    "risk_flags": ["ten levels a day is the most aggressive assumption here"],
}


@pytest.fixture
def plan():
    return Plan.from_dict(PLAN)


@pytest.fixture
def state():
    s = State(project="Neon Drift")
    s.task("t1").status = DONE
    s.task("t1").cost_usd = 1.99
    s.task("t1").pr_number, s.task("t1").pr_url = 12, "https://github.com/o/r/pull/12"
    s.task("t2").status = FAILED
    s.task("t2").attempts = 2
    s.task("t2").last_error = "AssertionError: expected reversal on the next tick"
    s.task("t3").status = PARKED
    s.task("t3").last_error = "the plan reserved this decision for you"
    return s


def payload_from(page):
    match = re.search(
        r'<script type="application/json" id="longhaul-data">(.*?)</script>', page, re.S)
    assert match, "the page must carry its data"
    return json.loads(match.group(1).replace("<\\/", "</"))


# --- the document ---------------------------------------------------------

def test_the_page_is_self_contained(plan, state):
    """It has to open from file://, a CI artefact, or an email attachment."""
    page = render.render(plan, state)
    assert "<style>" in page and "<script>" in page
    assert not re.search(r'(?:src|href)="https?://(?!github\.com/cybiqon-ai)', page)


def test_the_data_is_embedded_so_it_works_with_no_server(plan, state):
    body = payload_from(render.render(plan, state))
    assert body["project"] == "Neon Drift"
    assert len(body["tasks"]) == 3


def test_the_live_page_ships_no_data_because_it_fetches_it(plan, state):
    page = render.render(plan, state, live=True)
    assert 'id="longhaul-data"' not in page
    assert "/api/data" in page


# --- the payload ----------------------------------------------------------

def test_every_task_carries_its_criteria(plan, state):
    body = ui_data.build(plan, state)
    t1 = next(t for t in body["tasks"] if t["id"] == "t1")
    assert t1["criteria"] == ["flutter analyze exits 0"]
    assert t1["milestone"] == "Core loop"


def test_the_counts_reconcile_against_the_task_total(plan, state):
    body = ui_data.build(plan, state)
    assert sum(body["counts"].values()) == body["tasks_total"]


@pytest.mark.parametrize("status", [DONE, FAILED, PARKED, HALTED, "in_progress", "skipped"])
def test_the_counts_reconcile_for_every_status(plan, status):
    s = State()
    s.task("t1").status = status
    body = ui_data.build(plan, s)
    assert sum(body["counts"].values()) == body["tasks_total"], body["counts"]


def test_it_surfaces_why_something_failed_or_parked(plan, state):
    body = ui_data.build(plan, state)
    reasons = " ".join(t["last_error"] for t in body["tasks"])
    assert "expected reversal on the next tick" in reasons
    assert "reserved this decision" in reasons, "a parked task is the one a human must act on"


def test_it_carries_pr_links_and_risk_flags(plan, state):
    body = ui_data.build(plan, state)
    assert any(t["pr_url"] == "https://github.com/o/r/pull/12" for t in body["tasks"])
    assert "most aggressive assumption" in body["risk_flags"][0]


def test_the_day_series_covers_every_day_so_gaps_show_as_gaps(plan, state):
    body = ui_data.build(plan, state)
    assert [d["day"] for d in body["series"]] == [1, 2, 3]


def test_an_unstarted_task_is_pending(plan):
    body = ui_data.build(plan, State())
    assert {t["status"] for t in body["tasks"]} == {"pending"}
    assert body["counts"]["pending"] == 3


def test_the_ledger_becomes_the_runs_view(plan, state):
    ledger = [
        {"at": "2026-08-30T09:00:00+00:00", "task": "t1", "role": "coder",
         "attempt": 1, "session_id": "s1", "cost_usd": 1.99, "duration_s": 592.3, "ok": True},
    ]
    body = ui_data.build(plan, state, ledger)
    run = body["runs"][0]
    assert run["role"] == "coder" and run["day"] == 1
    assert run["title"] == "Scaffold", "a run must name the task it worked on"


# --- injection ------------------------------------------------------------

def test_a_closing_script_tag_in_agent_output_cannot_break_out(plan):
    """Agent output reaches this file verbatim, and it is embedded inside a
    <script> block — so `</script>` is the injection that matters here."""
    s = State()
    s.task("t1").status = FAILED
    s.task("t1").last_error = "</script><script>alert(1)</script>"
    page = render.render(plan, s)
    assert "</script><script>alert(1)" not in page
    body = payload_from(page)
    assert "alert(1)" in body["tasks"][0]["last_error"], "the text is kept, only made inert"


def test_markup_in_a_project_name_is_inert_everywhere_it_appears(plan):
    """It lands in two places with different rules.

    In the `<title>` it is HTML and must be escaped. Inside the JSON block it is
    not HTML — only `</script` can terminate that context — so it is carried
    verbatim and escaped again by the client before it reaches the DOM.
    """
    plan.project = "<img src=x onerror=alert(1)>"
    page = render.render(plan, State())

    head = page[: page.index("<style>")]
    assert "<img src=x" not in head, "the title must be escaped"
    assert "&lt;img" in head

    assert payload_from(page)["project"] == "<img src=x onerror=alert(1)>"


def test_no_unescaped_script_terminator_survives_in_the_payload(plan):
    s = State()
    s.task("t1").status = FAILED
    s.task("t1").last_error = "</SCRIPT foo"
    page = render.render(plan, s)
    body = page[page.index("longhaul-data"):]
    assert "</SCRIPT" not in body.split("</script>")[0]


# --- summary --------------------------------------------------------------

def test_summary_is_the_headline_numbers(plan, state):
    assert render.summary(plan, state) == {
        "project": "Neon Drift", "target_days": 3, "tasks": 3,
        "done": 1, "failed": 1, "parked": 1, "halted": 0,
        "in_progress": 0, "skipped": 0, "pending": 0,
        "total_cost_usd": 1.99,
    }


def test_json_output_is_parseable(plan, state):
    assert json.loads(render.to_json(plan, state))["done"] == 1


def test_write_produces_a_file(tmp_path, plan, state):
    out = render.write(plan, state, tmp_path / "sub" / "report.html")
    assert out.is_file() and out.stat().st_size > 5000
