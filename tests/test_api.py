"""The read-only JSON API the interface reads.

Nothing here writes. Actions belong to a shared command layer that both this and
the Telegram bot will call, and that does not exist yet.
"""

import json

import pytest
import yaml

from longhaul.core import registry, state as state_io, transcript
from longhaul.schema.state import DONE, PARKED, State
from longhaul.ui import api

PLAN = {
    "project": "Neon Drift", "target_days": 3, "profile": "flutter-android",
    "milestones": [{"id": "m1", "title": "Core", "tasks": [
        {"id": "t1", "day": 1, "title": "Scaffold", "acceptance_criteria": ["a"]},
        {"id": "t2", "day": 2, "title": "Loop", "acceptance_criteria": ["b"]},
    ]}],
}


@pytest.fixture
def home(isolate_longhaul_home):
    return isolate_longhaul_home


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "neon-drift"
    (root / ".longhaul").mkdir(parents=True)
    (root / ".longhaul" / "plan.yaml").write_text(yaml.safe_dump(PLAN))
    s = State(project="Neon Drift")
    s.task("t1").status = DONE
    s.task("t1").cost_usd = 1.99
    s.task("t2").status = PARKED
    s.task("t2").last_error = "reserved for you"
    state_io.save(s, root)
    registry.register(root)
    return root


# --- home ------------------------------------------------------------------

def test_the_home_list_summarises_without_opening_everything(project):
    row = api.projects()["projects"][0]
    assert row["id"] == "neon-drift"
    assert row["title"] == "Neon Drift"
    assert row["days_done"] == 1
    assert row["total_cost_usd"] == 1.99
    assert row["needs_you"] == 1, "a parked task is something waiting on a human"


def test_a_project_whose_directory_is_gone_is_listed_as_missing(project):
    import shutil

    shutil.rmtree(project / ".longhaul")
    row = api.projects()["projects"][0]
    assert row["status"] == "missing" and row["exists"] is False


def test_a_registered_project_with_no_plan_is_unplanned(tmp_path):
    root = tmp_path / "fresh"
    (root / ".longhaul").mkdir(parents=True)
    registry.register(root)
    row = api.projects()["projects"][0]
    assert row["status"] == "unplanned"
    assert "no plan" in row["problem"]


def test_an_unreadable_plan_does_not_take_the_home_screen_down(tmp_path):
    root = tmp_path / "broken"
    (root / ".longhaul").mkdir(parents=True)
    (root / ".longhaul" / "plan.yaml").write_text("project: ''\ntarget_days: 0\nmilestones: []\n")
    registry.register(root)
    row = api.projects()["projects"][0]
    assert row["status"] == "unplanned"
    assert "problem" in row


def test_no_projects_is_an_empty_list():
    assert api.projects() == {"projects": []}


# --- a project -------------------------------------------------------------

def test_project_data_carries_the_whole_payload(project):
    body = api.project_data("neon-drift")
    assert body["project"] == "Neon Drift"
    assert body["project_id"] == "neon-drift"
    assert len(body["tasks"]) == 2
    assert sum(body["counts"].values()) == body["tasks_total"]


def test_an_unknown_project_says_so_rather_than_crashing():
    assert "error" in api.project_data("nope")


def test_project_data_lists_available_transcripts(project):
    path = transcript.path_for(project, 1, "t1", "coder", 1)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"type": "result", "session_id": "s1"}) + "\n")
    body = api.project_data("neon-drift")
    assert body["transcripts"][0]["task"] == "t1"
    assert body["transcripts"][0]["role"] == "coder"


# --- transcripts -----------------------------------------------------------

def test_a_transcript_reads_back_as_a_conversation(project):
    path = transcript.path_for(project, 1, "t1", "coder", 1)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in [
        {"type": "assistant", "message": {"content": [
            {"type": "text", "text": "Scaffolding the app."}]}},
        {"type": "result", "session_id": "s1", "total_cost_usd": 1.99, "is_error": False},
    ]) + "\n")
    body = api.project_transcript("neon-drift", ".longhaul/runs/day-01/t1/coder-1.jsonl")
    assert body["messages"][0]["text"] == "Scaffolding the app."
    assert body["cost_usd"] == 1.99


@pytest.mark.parametrize("attack", [
    "../../../etc/passwd",
    ".longhaul/runs/../../../etc/passwd",
    ".longhaul/state.json",
    "../.longhaul/plan.yaml",
])
def test_a_transcript_id_cannot_read_outside_the_runs_directory(project, attack):
    """The id comes from a URL, so this has to be proven rather than assumed."""
    assert api.project_transcript("neon-drift", attack) == {"error": "not found"}


def test_a_missing_transcript_is_not_found(project):
    assert api.project_transcript("neon-drift", ".longhaul/runs/day-09/t9/coder-1.jsonl") == {
        "error": "not found"}


def test_a_transcript_for_an_unknown_project_says_so():
    assert "error" in api.project_transcript("nope", "x.jsonl")
