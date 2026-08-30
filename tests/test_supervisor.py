"""Ceilings and loop detection, enforced outside the agent.

An agent told to respect a budget is an agent that will report having respected
the budget.
"""

from longhaul.core import supervisor
from longhaul.schema.config import Config, Limits
from longhaul.schema.plan import Task
from longhaul.schema.state import State


def task():
    return Task(id="t1", day=1, title="x", acceptance_criteria=["y"])


def cfg(**kw):
    return Config(limits=Limits(**kw))


# --- fingerprints ---------------------------------------------------------

def test_the_same_failure_twice_has_the_same_fingerprint():
    a = "FAILED /tmp/pytest-of-x/test_abc123/t.py::test_login in 1.24s"
    b = "FAILED /tmp/pytest-of-x/test_zzz999/t.py::test_login in 3.01s"
    assert supervisor.fingerprint(a) == supervisor.fingerprint(b)


def test_different_failures_have_different_fingerprints():
    assert supervisor.fingerprint("assert 1 == 2") != supervisor.fingerprint("NameError: foo")


def test_no_error_has_no_fingerprint():
    assert supervisor.fingerprint(None) == "" and supervisor.fingerprint("") == ""


# --- ceilings -------------------------------------------------------------

def test_project_ceiling_halts_the_project():
    s = State()
    s.task("t0").cost_usd = 200.0
    halt = supervisor.check_before(s, s.task("t1"), task(), cfg(cost_usd_total=200.0))
    assert halt and halt.scope == "project"
    assert "project ceiling" in halt.reason


def test_daily_ceiling_counts_only_today():
    s = State()
    old = s.task("old")
    old.cost_usd, old.finished_at = 50.0, "2020-01-01T00:00:00+00:00"
    assert supervisor.spent_today(s) == 0.0
    assert supervisor.check_before(s, s.task("t1"), task(), cfg(cost_usd_per_day=20.0)) is None


def test_daily_ceiling_halts_once_today_is_spent():
    from longhaul.schema.state import now
    s = State()
    today = s.task("today")
    today.cost_usd, today.finished_at = 25.0, now()
    halt = supervisor.check_before(s, s.task("t1"), task(), cfg(cost_usd_per_day=20.0))
    assert halt and "daily ceiling" in halt.reason


def test_per_task_ceiling_halts_only_that_task():
    s = State()
    ts = s.task("t1")
    ts.cost_usd = 6.0
    halt = supervisor.check_before(s, ts, task(), cfg(cost_usd_per_task=5.0))
    assert halt and halt.scope == "task"


def test_attempt_budget_halts_the_task():
    s = State()
    ts = s.task("t1")
    ts.attempts = 3
    halt = supervisor.check_before(s, ts, task(), cfg(max_attempts=3))
    assert halt and "all 3 attempts" in halt.reason


# --- loop detection -------------------------------------------------------

def test_the_same_error_twice_running_halts_before_the_budget_runs_out():
    """The failure the Supervisor exists for: retrying something deterministic."""
    s = State()
    ts = s.task("t1")
    for _ in range(2):
        supervisor.record_failure(ts, "AssertionError: expected 1, got 2")
    halt = supervisor.check_before(s, ts, task(), cfg(identical_failures=2, max_attempts=5))
    assert halt and "same error 2 times" in halt.reason


def test_different_errors_are_not_a_loop():
    s = State()
    ts = s.task("t1")
    supervisor.record_failure(ts, "AssertionError: a")
    supervisor.record_failure(ts, "NameError: b")
    assert supervisor.check_before(s, ts, task(), cfg(identical_failures=2)) is None


def test_a_repeat_after_a_different_error_still_counts_from_the_break():
    s = State()
    ts = s.task("t1")
    for e in ("same", "different", "same"):
        supervisor.record_failure(ts, e)
    assert supervisor.check_before(s, ts, task(), cfg(identical_failures=2)) is None


def test_a_fresh_task_is_never_halted():
    s = State()
    assert supervisor.check_before(s, s.task("t1"), task(), Config()) is None


def test_different_assertion_values_are_not_the_same_failure():
    """Stripping every number would make an agent's real progress look like a loop.

    A missed loop costs one retry. A false loop costs the whole task.
    """
    a = supervisor.fingerprint("AssertionError: expected 1, got 2")
    b = supervisor.fingerprint("AssertionError: expected 3, got 4")
    assert a != b


def test_durations_and_temp_paths_are_still_normalised():
    a = "FAILED /tmp/pytest-of-x/abc/t.py::test_login in 1.24s"
    b = "FAILED /tmp/pytest-of-x/zzz/t.py::test_login in 30.9s"
    assert supervisor.fingerprint(a) == supervisor.fingerprint(b)


def test_git_shas_are_normalised():
    a = supervisor.fingerprint("failed to apply 8c02271fdb2a")
    b = supervisor.fingerprint("failed to apply 0217e8e346cf")
    assert a == b
