"""The static report: one self-contained file, openable with no network.

It is the debugging surface for the orchestrator — reading state.json by hand
stops working around day three — and the page a reader sees before the code.
"""

import re

import pytest

from longhaul.schema.plan import Plan
from longhaul.schema.state import DONE, FAILED, HALTED, PARKED, State
from longhaul.ui import render

PLAN = {
    "project": "Neon Drift", "target_days": 3, "profile": "flutter-android",
    "milestones": [{"id": "m1", "title": "Core", "tasks": [
        {"id": "t1", "day": 1, "title": "Scaffold",
         "acceptance_criteria": ["flutter analyze exits 0"]},
        {"id": "t2", "day": 2, "title": "Core loop", "depends_on": ["t1"],
         "acceptance_criteria": ["a tap reverses direction"]},
        {"id": "t3", "day": 3, "title": "Pick the palette", "needs_human": True,
         "acceptance_criteria": ["the author chose one"]},
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
    s.task("t3").last_error = "the plan reserved this decision for a human"
    return s


def test_the_page_is_self_contained(plan, state):
    """No network: it has to open from file://, a CI artifact, or a machine that
    never ran the agent."""
    page = render.render(plan, state)
    assert "<style>" in page and "</style>" in page
    assert not re.search(r'<(?:link|script)[^>]*\bsrc=|<link[^>]*\bhref="http', page)
    assert "http://" not in page.replace("http://www.w3.org", "")


def test_it_shows_every_task_with_its_criteria(plan, state):
    page = render.render(plan, state)
    for title in ("Scaffold", "Core loop", "Pick the palette"):
        assert title in page
    assert "flutter analyze exits 0" in page
    assert "a tap reverses direction" in page


def test_it_reports_counts_not_a_status(plan, state):
    page = render.render(plan, state)
    for label in ("done", "failed", "parked", "to go", "spent"):
        assert f">{label}<" in page
    assert "$1.99" in page


def test_it_surfaces_why_something_failed_or_parked(plan, state):
    page = render.render(plan, state)
    assert "expected reversal on the next tick" in page
    assert "reserved this decision for a human" in page


def test_it_links_open_prs(plan, state):
    assert 'href="https://github.com/o/r/pull/12"' in render.render(plan, state)


def test_it_shows_the_risk_flags(plan, state):
    assert "most aggressive assumption" in render.render(plan, state)


def test_an_unstarted_task_shows_as_pending(plan):
    page = render.render(plan, State())
    assert page.count('class="pending"') == 3


def test_html_in_a_project_name_or_error_cannot_break_the_page(plan):
    """Agent output ends up here verbatim; a stack trace must not inject markup."""
    plan.project = "<script>alert(1)</script>"
    s = State()
    s.task("t1").status = FAILED
    s.task("t1").last_error = "<img src=x onerror=alert(1)>"
    page = render.render(plan, s)
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page
    assert "onerror=alert(1)>" not in page


def test_write_produces_a_file(tmp_path, plan, state):
    out = render.write(plan, state, tmp_path / "sub" / "report.html")
    assert out.is_file() and out.stat().st_size > 1000


def test_summary_matches_the_page(plan, state):
    s = render.summary(plan, state)
    assert s == {
        "project": "Neon Drift", "target_days": 3, "tasks": 3,
        "done": 1, "failed": 1, "parked": 1, "halted": 0,
        "in_progress": 0, "skipped": 0, "pending": 0,
        "total_cost_usd": 1.99,
    }


def test_summary_counts_unstarted_tasks_as_pending(plan):
    assert render.summary(plan, State())["pending"] == 3


def test_json_output_is_parseable(plan, state):
    import json

    assert json.loads(render.to_json(plan, state))["done"] == 1


def test_a_parked_task_shows_why_it_is_waiting(plan):
    """Parked tasks are the ones a human has to act on — hiding the reason
    hides the only thing they need to read."""
    s = State()
    s.task("t3").status = PARKED
    s.task("t3").last_error = "the plan reserved this decision for a human"
    assert "reserved this decision" in render.render(plan, s)


def test_a_halted_task_shows_its_ceiling(plan):
    s = State()
    s.task("t1").status = HALTED
    s.task("t1").last_error = "daily ceiling reached: $20.14 of $20.00 spent today"
    assert "daily ceiling reached" in render.render(plan, s)


@pytest.mark.parametrize("status", [DONE, FAILED, PARKED, HALTED, "in_progress", "skipped"])
def test_the_counts_always_reconcile_against_the_task_total(plan, status):
    """A summary whose parts do not add up to the whole is the failure this
    project is named for. An in-progress task went missing from an earlier
    version of exactly this line."""
    s = State()
    s.task("t1").status = status
    summary = render.summary(plan, s)
    buckets = ("done", "failed", "parked", "halted", "in_progress", "skipped", "pending")
    assert sum(summary[b] for b in buckets) == summary["tasks"], summary
