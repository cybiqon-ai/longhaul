"""Ask a model to look at the artefact and judge it against the criteria.

This is the one place a model's opinion is load-bearing, and it is deliberately
narrow: it is shown an artefact and the acceptance criteria, and returns a
structured verdict. It cannot edit anything — read-only tools, asserted by a
test — so the thing being judged cannot be changed by its judge.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .. import roles
from ..driver.base import AgentDriver, AgentRequest
from ..schema.plan import Plan, Task

#: Read-only. The inspector must not be able to alter what it is inspecting.
INSPECTOR_TOOLS = ["Read", "Glob", "Grep"]

DESIGN_SYSTEM_CANDIDATES = (
    "docs/design-system.md",
    "design/design-system.md",
    "DESIGN.md",
)

VERDICT_SCHEMA = {
    "type": "object",
    "required": ["passes", "observed", "confidence"],
    "properties": {
        "passes": {"type": "boolean"},
        "observed": {
            "type": "string",
            "description": "what is actually in the artefact, before judging it",
        },
        "problems": {
            "type": "array",
            "items": {"type": "string"},
            "description": "specific, actionable; this text goes back to the agent",
        },
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
    },
}


@dataclass
class Verdict:
    passes: bool
    observed: str = ""
    problems: list[str] | None = None
    confidence: str = "low"
    cost_usd: float = 0.0
    ran: bool = True
    detail: str = ""

    def summary(self) -> str:
        if not self.ran:
            return f"not inspected: {self.detail}"
        state = "passes" if self.passes else "FAILS"
        problems = ("; ".join(self.problems or []))[:300]
        return f"inspector {state} ({self.confidence})" + (f" — {problems}" if problems else "")


def find_design_system(worktree: Path) -> Path | None:
    for name in DESIGN_SYSTEM_CANDIDATES:
        path = worktree / name
        if path.is_file():
            return path
    return None


def build_prompt(plan: Plan, task: Task, artefacts: list[Path], worktree: Path) -> str:
    lines = [
        f"Project: {plan.project}",
        f"Day {task.day} — {task.title}",
        "",
        "## Acceptance criteria",
        *[f"  - {c}" for c in task.acceptance_criteria],
    ]
    if task.proof and task.proof.expect:
        lines += ["", "## What the artefact must show", "", task.proof.expect]

    lines += ["", "## Artefact(s) to look at", ""]
    for path in artefacts:
        try:
            rel = path.relative_to(worktree)
        except ValueError:
            rel = path
        lines.append(f"  {rel}")

    design = find_design_system(worktree)
    if design:
        lines += ["", f"The project's design system is at `{design.name}` — check against it."]
    return "\n".join(lines)


def run(
    driver: AgentDriver,
    plan: Plan,
    task: Task,
    artefacts: list[Path],
    worktree: Path,
    model: str | None = None,
) -> Verdict:
    if not artefacts:
        return Verdict(passes=False, ran=False, detail="there was no artefact to look at")

    result = driver.run(
        AgentRequest(
            prompt=build_prompt(plan, task, artefacts, worktree),
            role="inspector",
            cwd=str(worktree),
            allowed_tools=INSPECTOR_TOOLS,
            append_system_prompt=roles.load("inspector"),
            json_schema=VERDICT_SCHEMA,
            model=model,
        )
    )

    if not result.ok or not result.structured:
        # Could not judge is not the same as judged and passed.
        return Verdict(
            passes=False, ran=False, cost_usd=result.cost_usd,
            detail=result.error or "the inspector returned no structured verdict",
        )

    data = result.structured
    return Verdict(
        passes=bool(data.get("passes")),
        observed=str(data.get("observed", "")),
        problems=[str(p) for p in data.get("problems") or []],
        confidence=str(data.get("confidence", "low")),
        cost_usd=result.cost_usd,
    )
