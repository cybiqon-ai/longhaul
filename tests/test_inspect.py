"""The Inspector — the one place a model's opinion is load-bearing.

Deliberately narrow: shown an artefact and the criteria, returns a structured
verdict, and cannot edit the thing it is judging.
"""


import pytest

from longhaul.core import inspect as inspect_mod
from longhaul.driver.base import AgentResult
from longhaul.schema.plan import Plan

PLAN = {
    "project": "Neon Drift", "target_days": 2, "profile": "flutter-android",
    "milestones": [{"id": "m1", "title": "Core", "tasks": [
        {"id": "t1", "day": 1, "title": "First playable",
         "acceptance_criteria": ["the loop and the dot render"],
         "proof": {"kind": "emulator_screenshot",
                   "expect": "a moving dot on a loop, dark theme, no debug banner"}},
    ]}],
}


class FakeDriver:
    def __init__(self, result):
        self.result = result
        self.request = None

    def run(self, request):
        self.request = request
        return self.result


def plan():
    return Plan.from_dict(PLAN)


@pytest.fixture
def shot(tmp_path):
    path = tmp_path / "screenshot.png"
    path.write_bytes(b"\x89PNG\r\n")
    return path


def verdict(**kw):
    payload = {"passes": True, "observed": "a dot on a loop", "confidence": "high"}
    payload.update(kw)
    return AgentResult(ok=True, text="", structured=payload, cost_usd=0.04)


def test_the_inspector_cannot_edit_what_it_judges(tmp_path, shot):
    driver = FakeDriver(verdict())
    inspect_mod.run(driver, plan(), plan().task("t1"), [shot], tmp_path)
    tools = set(driver.request.allowed_tools)
    assert tools == {"Read", "Glob", "Grep"}
    assert not {"Edit", "Write", "Bash"} & tools


def test_the_prompt_carries_the_criteria_the_expectation_and_the_artefact(tmp_path, shot):
    driver = FakeDriver(verdict())
    inspect_mod.run(driver, plan(), plan().task("t1"), [shot], tmp_path)
    prompt = driver.request.prompt
    assert "the loop and the dot render" in prompt
    assert "no debug banner" in prompt
    assert "screenshot.png" in prompt
    assert driver.request.json_schema is not None
    assert "You are the Inspector" in driver.request.append_system_prompt


def test_a_pass_is_a_pass(tmp_path, shot):
    v = inspect_mod.run(FakeDriver(verdict()), plan(), plan().task("t1"), [shot], tmp_path)
    assert v.passes and v.ran and v.cost_usd == 0.04


def test_a_failure_carries_the_problems_back(tmp_path, shot):
    result = verdict(passes=False, problems=["the screen is grey", "no dot visible"],
                     confidence="high")
    v = inspect_mod.run(FakeDriver(result), plan(), plan().task("t1"), [shot], tmp_path)
    assert not v.passes
    assert "the screen is grey" in v.summary()


def test_no_artefact_means_it_did_not_run_rather_than_passed(tmp_path):
    """Could not judge is not the same as judged and passed."""
    driver = FakeDriver(verdict())
    v = inspect_mod.run(driver, plan(), plan().task("t1"), [], tmp_path)
    assert not v.ran and not v.passes
    assert driver.request is None, "it must not spend anything with nothing to look at"


def test_an_agent_failure_is_not_a_pass(tmp_path, shot):
    v = inspect_mod.run(
        FakeDriver(AgentResult(ok=False, text="", error="rate_limit")),
        plan(), plan().task("t1"), [shot], tmp_path)
    assert not v.ran and not v.passes and "rate_limit" in v.detail


def test_unstructured_output_is_not_a_pass(tmp_path, shot):
    v = inspect_mod.run(
        FakeDriver(AgentResult(ok=True, text="looks good to me!", structured=None)),
        plan(), plan().task("t1"), [shot], tmp_path)
    assert not v.ran and not v.passes


def test_it_points_at_the_design_system_when_one_exists(tmp_path, shot):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "design-system.md").write_text("# tokens\n")
    driver = FakeDriver(verdict())
    inspect_mod.run(driver, plan(), plan().task("t1"), [shot], tmp_path)
    assert "design-system.md" in driver.request.prompt


def test_it_says_nothing_about_a_design_system_when_there_is_none(tmp_path, shot):
    driver = FakeDriver(verdict())
    inspect_mod.run(driver, plan(), plan().task("t1"), [shot], tmp_path)
    assert "design system" not in driver.request.prompt.lower()


def test_the_schema_demands_a_reason_not_just_a_boolean():
    schema = inspect_mod.VERDICT_SCHEMA
    assert set(schema["required"]) == {"passes", "observed", "confidence"}
    assert schema["properties"]["confidence"]["enum"] == ["low", "medium", "high"]


def test_the_prompt_tells_it_a_false_pass_is_the_expensive_one():
    from longhaul import roles

    body = roles.load("inspector")
    assert "false pass" in body.lower()
    assert "grey" in body.lower(), "the common failure modes must be listed"
