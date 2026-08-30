"""Run the Planner and turn its answer into a validated Plan.

The Planner is the only role that may not write anything. It is given read-only
tools deliberately: a planning step that edits the repository is a planning step
you cannot re-run.
"""

from __future__ import annotations

from pathlib import Path

from .. import profiles, roles
from ..driver.base import AgentDriver, AgentRequest
from ..schema.plan import Plan, PlanError, json_schema

#: Read-only. The Planner reads the repo to plan against it and changes nothing.
PLANNER_TOOLS = ["Read", "Glob", "Grep"]

PLAN_PATH = Path(".longhaul/plan.yaml")


def build_prompt(target_text: str, days: int, profile_name: str) -> str:
    parts = [
        f"Plan this project across exactly {days} days.",
        "",
        "## Target",
        "",
        target_text.strip(),
        "",
        "## Stack",
        "",
        profiles.summarise(profile_name),
        "",
        f"Return JSON matching the schema, with `target_days` = {days} and "
        f"`profile` = {profile_name!r}.",
    ]
    return "\n".join(parts)


def run(
    driver: AgentDriver,
    target: Path,
    days: int,
    profile_name: str,
    cwd: Path | None = None,
    model: str | None = None,
) -> tuple[Plan, float]:
    """Plan the project. Returns the validated plan and what it cost in USD."""
    if days < 1:
        raise ValueError(f"days must be >= 1, got {days}")
    if not target.is_file():
        raise FileNotFoundError(f"no target file at {target}")
    profiles.load(profile_name)  # raises early on an unknown profile

    result = driver.run(
        AgentRequest(
            prompt=build_prompt(target.read_text(encoding="utf-8"), days, profile_name),
            role="planner",
            cwd=str(cwd or Path.cwd()),
            allowed_tools=PLANNER_TOOLS,
            append_system_prompt=roles.load("planner"),
            json_schema=json_schema(),
            model=model,
        )
    )

    if not result.ok:
        raise PlanError([f"the planner failed: {result.error or 'no error reported'}"])
    if not result.structured:
        raise PlanError(
            ["the planner returned no structured output — the JSON schema was not honoured"]
        )

    payload = dict(result.structured)
    payload.setdefault("profile", profile_name)
    payload.setdefault("target_days", days)
    return Plan.from_dict(payload), result.cost_usd


def render(plan: Plan) -> str:
    """The day-by-day arc, for `simulate` and for reading a plan back."""
    lines = [
        f"{plan.project}",
        f"{plan.target_days} days · {plan.profile} · "
        f"{len(plan.milestones)} milestones · {len(plan.tasks)} tasks",
        "",
    ]
    by_milestone = {m.id: m for m in plan.milestones}
    seen_milestones: set[str] = set()

    for day in range(1, plan.target_days + 1):
        tasks = plan.tasks_for_day(day)
        if not tasks:
            lines.append(f"  day {day:>2}  —  (slack)")
            continue
        for task in tasks:
            milestone = next(
                (m for m in by_milestone.values() if task in m.tasks), None
            )
            if milestone and milestone.id not in seen_milestones:
                seen_milestones.add(milestone.id)
                lines.append(f"  ── {milestone.title} ──")
            flags = []
            if task.needs_human:
                flags.append("NEEDS YOU")
            if task.risk != "low":
                flags.append(f"risk:{task.risk}")
            suffix = ("   " + " ".join(flags)) if flags else ""
            lines.append(f"  day {day:>2}  {task.id:<4} {task.title}{suffix}")
            for criterion in task.acceptance_criteria:
                lines.append(f"           · {criterion}")

    if plan.risk_flags:
        lines += ["", "  risk flags:"]
        lines += [f"    ! {r}" for r in plan.risk_flags]

    planned = len({t.day for t in plan.tasks})
    lines += [
        "",
        f"  days planned: {planned}/{plan.target_days}   "
        f"tasks: {len(plan.tasks)}   "
        f"needs a human: {sum(1 for t in plan.tasks if t.needs_human)}",
    ]
    return "\n".join(lines)
