"""The Planner, driven by a fake so the suite runs offline with no credentials."""

from pathlib import Path

import pytest

from longhaul import profiles
from longhaul.core import planner
from longhaul.driver.base import AgentResult
from longhaul.schema.plan import PlanError

GOOD = {
    "project": "Neon Drift",
    "target_days": 2,
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
                    "proof": {"kind": "emulator_screenshot", "expect": "a launch screen"},
                },
                {
                    "id": "t2",
                    "day": 2,
                    "title": "Tap to reverse",
                    "acceptance_criteria": ["a tap reverses direction"],
                    "depends_on": ["t1"],
                    "needs_human": True,
                    "risk": "high",
                },
            ],
        }
    ],
    "risk_flags": ["levels 20-30 will not fit in 2 days"],
}


class FakeDriver:
    def __init__(self, result):
        self.result = result
        self.request = None

    def run(self, request):
        self.request = request
        return self.result


def ok(structured=None, **kw):
    return AgentResult(ok=True, text="", structured=structured or GOOD, cost_usd=0.37, **kw)


@pytest.fixture
def target(tmp_path):
    p = tmp_path / "target.md"
    p.write_text("# Neon Drift\n\nA one-thumb arcade game.\n")
    return p


def test_plans_and_reports_cost(target):
    driver = FakeDriver(ok())
    plan, cost = planner.run(driver, target, days=2, profile_name="flutter-android")
    assert plan.project == "Neon Drift"
    assert cost == 0.37
    assert len(plan.tasks) == 2


def test_the_planner_gets_read_only_tools(target):
    """A planning step that can edit the repo is one you cannot safely re-run."""
    driver = FakeDriver(ok())
    planner.run(driver, target, days=2, profile_name="flutter-android")
    tools = driver.request.allowed_tools
    assert tools == ["Read", "Glob", "Grep"]
    assert not {"Edit", "Write", "Bash", "NotebookEdit"} & set(tools)


def test_the_prompt_carries_the_target_the_days_and_the_stack(target):
    driver = FakeDriver(ok())
    planner.run(driver, target, days=9, profile_name="flutter-android")
    prompt = driver.request.prompt
    assert "one-thumb arcade game" in prompt
    assert "exactly 9 days" in prompt
    assert "flutter analyze" in prompt  # from the profile
    assert driver.request.json_schema is not None
    assert "▶ STEP 1" in driver.request.append_system_prompt


def test_a_failed_agent_run_is_not_an_empty_plan(target):
    driver = FakeDriver(AgentResult(ok=False, text="", error="rate_limit"))
    with pytest.raises(PlanError) as exc:
        planner.run(driver, target, days=2, profile_name="flutter-android")
    assert "rate_limit" in exc.value.problems[0]


def test_missing_structured_output_is_a_failure(target):
    driver = FakeDriver(AgentResult(ok=True, text="here is your plan!", structured=None))
    with pytest.raises(PlanError) as exc:
        planner.run(driver, target, days=2, profile_name="flutter-android")
    assert "structured" in exc.value.problems[0]


def test_an_invalid_plan_from_the_model_is_rejected(target):
    bad = {**GOOD, "milestones": [{"id": "m1", "title": "x", "tasks": [
        {"id": "t1", "day": 1, "title": "no criteria", "acceptance_criteria": []}]}]}
    with pytest.raises(PlanError):
        planner.run(FakeDriver(ok(bad)), target, days=2, profile_name="flutter-android")


def test_unknown_profile_fails_before_spending_anything(target):
    driver = FakeDriver(ok())
    with pytest.raises(FileNotFoundError):
        planner.run(driver, target, days=2, profile_name="cobol-mainframe")
    assert driver.request is None, "must not call the model with an unknown profile"


def test_missing_target_fails_before_spending_anything(tmp_path):
    driver = FakeDriver(ok())
    with pytest.raises(FileNotFoundError):
        planner.run(driver, tmp_path / "nope.md", days=2, profile_name="flutter-android")
    assert driver.request is None


def test_render_shows_days_criteria_flags_and_counts(target):
    plan, _ = planner.run(FakeDriver(ok()), target, days=2, profile_name="flutter-android")
    out = planner.render(plan)
    assert "day  1" in out and "day  2" in out
    assert "a tap reverses direction" in out
    assert "NEEDS YOU" in out and "risk:high" in out
    assert "levels 20-30 will not fit" in out
    assert "days planned: 2/2" in out
    assert "needs a human: 1" in out


def test_render_marks_unplanned_days_as_slack(target):
    plan, _ = planner.run(FakeDriver(ok({**GOOD, "target_days": 4})), target,
                          days=4, profile_name="flutter-android")
    assert "(slack)" in planner.render(plan)


def test_profiles_are_discoverable_and_summarised():
    assert "flutter-android" in profiles.available()
    assert "flutter analyze" in profiles.summarise("flutter-android")
    with pytest.raises(FileNotFoundError):
        profiles.load("nope")


def test_every_shipped_profile_loads_and_declares_the_essentials():
    for name in profiles.available():
        p = profiles.load(name)
        assert p.get("commands", {}).get("test"), f"{name} has no test command"
        assert p.get("requires"), f"{name} declares no required binaries"
        assert (p.get("proof") or {}).get("kind"), f"{name} has no proof kind"


def test_planner_prompt_ships_with_the_package():
    from longhaul import roles
    assert Path(roles.DIR / "planner.md").is_file()
    assert "acceptance criteria" in roles.load("planner").lower()


def test_the_shipped_example_plan_is_valid():
    """A real Planner output, committed unedited. If the schema drifts, this breaks."""
    import yaml

    from longhaul.schema.plan import Plan

    root = Path(__file__).resolve().parents[1]
    plan = Plan.from_dict(yaml.safe_load((root / "examples/android-game/plan.yaml").read_text()))
    assert plan.target_days == 14
    assert len({t.day for t in plan.tasks}) == 14, "every day should carry work"
    assert any(t.needs_human for t in plan.tasks)
    assert plan.risk_flags
