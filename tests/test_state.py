"""State is the whole memory of a run, so it is written atomically and read back
tolerantly. A half-written state.json loses a fortnight of context."""

import json

from longhaul.core import state as state_io
from longhaul.schema.state import DONE, FAILED, PARKED, PENDING, State


def test_missing_state_is_an_empty_state_not_an_error(tmp_path):
    assert state_io.load(tmp_path).tasks == {}


def test_round_trips_through_disk(tmp_path):
    s = State(project="Neon Drift")
    s.task("t1").status = DONE
    s.task("t1").cost_usd = 0.5
    state_io.save(s, tmp_path)
    back = state_io.load(tmp_path)
    assert back.project == "Neon Drift"
    assert back.tasks["t1"].status == DONE
    assert back.total_cost_usd == 0.5


def test_writes_are_atomic_and_leave_no_temp_file(tmp_path):
    state_io.save(State(project="x"), tmp_path)
    files = {p.name for p in (tmp_path / ".longhaul").iterdir()}
    assert files == {"state.json"}


def test_tasks_are_created_lazily_so_a_replan_can_add_them():
    s = State()
    assert s.task("new").status == PENDING
    assert "new" in s.tasks


def test_counts_report_every_status():
    s = State()
    s.task("a").status = DONE
    s.task("b").status = FAILED
    s.task("c").status = PARKED
    counts = s.counts()
    assert counts["done"] == 1 and counts["failed"] == 1 and counts["parked"] == 1


def test_only_done_and_skipped_are_settled():
    s = State()
    s.task("a").status = DONE
    s.task("b").status = FAILED
    s.task("c").status = PARKED
    assert s.is_settled("a")
    assert not s.is_settled("b"), "failed is retryable, not settled"
    assert not s.is_settled("c"), "parked needs a human, so dependents must wait"


def test_unknown_status_is_rejected_rather_than_silently_accepted():
    import pytest

    with pytest.raises(ValueError, match="unknown status"):
        State.from_dict({"tasks": {"t1": {"id": "t1", "status": "vibing"}}})


def test_unknown_fields_are_ignored_so_an_older_state_still_loads():
    s = State.from_dict({"tasks": {"t1": {"id": "t1", "status": DONE, "future_field": 9}}})
    assert s.tasks["t1"].status == DONE


def test_ledger_is_append_only(tmp_path):
    state_io.append_ledger({"task": "t1", "cost_usd": 0.1}, tmp_path)
    state_io.append_ledger({"task": "t2", "cost_usd": 0.2}, tmp_path)
    entries = state_io.read_ledger(tmp_path)
    assert [e["task"] for e in entries] == ["t1", "t2"]


def test_a_torn_ledger_line_does_not_lose_the_rest(tmp_path):
    """A run killed mid-write leaves a partial final line. Keep the good ones."""
    path = tmp_path / ".longhaul" / "ledger.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"task": "t1"}) + "\n" + '{"task": "t2", "cos')
    assert [e["task"] for e in state_io.read_ledger(tmp_path)] == ["t1"]
