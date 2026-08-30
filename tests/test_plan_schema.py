"""The plan is a contract, so it is validated hard rather than trusted.

A plan that parses but is self-contradictory would not fail here — it would fail
silently on day 6, which is the expensive place to find out.
"""

import pytest

from longhaul.schema.plan import Plan, PlanError, json_schema


def make(**over):
    base = {
        "project": "Neon Drift",
        "target_days": 3,
        "profile": "flutter-android",
        "milestones": [
            {
                "id": "m1",
                "title": "Core loop",
                "tasks": [
                    {
                        "id": "t1",
                        "day": 1,
                        "title": "Scaffold + CI",
                        "acceptance_criteria": ["flutter test runs in CI"],
                    },
                    {
                        "id": "t2",
                        "day": 2,
                        "title": "Tap to reverse",
                        "acceptance_criteria": ["a tap reverses direction"],
                        "depends_on": ["t1"],
                    },
                ],
            }
        ],
    }
    base.update(over)
    return base


def problems_of(d):
    with pytest.raises(PlanError) as exc:
        Plan.from_dict(d)
    return exc.value.problems


def test_a_good_plan_parses():
    plan = Plan.from_dict(make())
    assert plan.project == "Neon Drift"
    assert len(plan.tasks) == 2
    assert plan.task("t2").depends_on == ["t1"]
    assert [t.id for t in plan.tasks_for_day(1)] == ["t1"]


def test_round_trips_through_dict():
    plan = Plan.from_dict(make())
    assert Plan.from_dict(plan.to_dict()).to_dict() == plan.to_dict()


def test_rejects_a_task_with_no_acceptance_criteria():
    d = make()
    d["milestones"][0]["tasks"][1]["acceptance_criteria"] = []
    assert any("acceptance_criteria" in p for p in problems_of(d))


def test_rejects_a_dependency_on_a_later_day():
    d = make()
    d["milestones"][0]["tasks"][0]["depends_on"] = ["t2"]
    assert any("scheduled later" in p for p in problems_of(d))


def test_rejects_a_dependency_cycle():
    d = make()
    d["milestones"][0]["tasks"][0]["depends_on"] = ["t2"]
    d["milestones"][0]["tasks"][1]["day"] = 1
    assert any("cycle" in p for p in problems_of(d))


def test_rejects_an_unknown_dependency():
    d = make()
    d["milestones"][0]["tasks"][1]["depends_on"] = ["nope"]
    assert any("unknown task" in p for p in problems_of(d))


def test_rejects_duplicate_ids():
    d = make()
    d["milestones"][0]["tasks"][1]["id"] = "t1"
    assert any("duplicate" in p for p in problems_of(d))


def test_rejects_a_day_past_the_deadline():
    d = make(target_days=1)
    assert any("outside 1..1" in p for p in problems_of(d))


def test_rejects_an_unknown_kind_and_risk():
    d = make()
    d["milestones"][0]["tasks"][0]["kind"] = "vibes"
    d["milestones"][0]["tasks"][0]["risk"] = "extreme"
    found = problems_of(d)
    assert any("kind" in p for p in found)
    assert any("risk" in p for p in found)


def test_reports_every_problem_not_just_the_first():
    d = make(project="", target_days=0)
    d["milestones"][0]["tasks"][0]["acceptance_criteria"] = []
    assert len(problems_of(d)) >= 3


def test_empty_plan_is_rejected():
    assert any("milestones" in p for p in problems_of(make(milestones=[])))


def test_json_schema_demands_checkable_criteria():
    task = json_schema()["properties"]["milestones"]["items"]["properties"]["tasks"]["items"]
    assert task["properties"]["acceptance_criteria"]["minItems"] == 1
    assert set(task["required"]) >= {"id", "day", "title", "acceptance_criteria"}
