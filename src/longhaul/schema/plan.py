"""The `plan.yaml` contract.

This is the single artifact the Planner produces and every other role consumes.
The Reviewer checks a diff against a task's `acceptance_criteria`; the DevOps
role reads `profile`; the Proof gate reads `proof`. So the schema is validated
hard at the boundary rather than trusted — a plan that parses but is
self-contradictory (a task depending on a later day, a dependency cycle, a task
with no acceptance criteria) would fail silently days into a run.

The wide-schema decision: fields consumed by roles that do not exist yet
(`kind`, `surfaces`, `needs_human`, `proof`) ship now, so stored plans do not
need rewriting when those roles land.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

KINDS = ("feature", "design", "asset", "docs", "infra", "fix")
RISKS = ("low", "medium", "high")


class PlanError(ValueError):
    """A plan that cannot be trusted. Carries every problem, not just the first."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__(f"{len(problems)} problem(s):\n  - " + "\n  - ".join(problems))


@dataclass
class Proof:
    kind: str
    expect: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Proof:
        return cls(kind=str(d.get("kind", "")), expect=str(d.get("expect", "")))

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "expect": self.expect}


@dataclass
class Task:
    id: str
    day: int
    title: str
    acceptance_criteria: list[str] = field(default_factory=list)
    kind: str = "feature"
    depends_on: list[str] = field(default_factory=list)
    surfaces: list[str] = field(default_factory=list)
    estimate_minutes: int = 60
    risk: str = "low"
    needs_human: bool = False
    proof: Proof | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Task:
        proof = d.get("proof")
        return cls(
            id=str(d.get("id", "")),
            day=int(d.get("day", 0) or 0),
            title=str(d.get("title", "")),
            acceptance_criteria=[str(c) for c in d.get("acceptance_criteria") or []],
            kind=str(d.get("kind", "feature")),
            depends_on=[str(x) for x in d.get("depends_on") or []],
            surfaces=[str(x) for x in d.get("surfaces") or []],
            estimate_minutes=int(d.get("estimate_minutes", 60) or 60),
            risk=str(d.get("risk", "low")),
            needs_human=bool(d.get("needs_human", False)),
            proof=Proof.from_dict(proof) if isinstance(proof, dict) else None,
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "day": self.day,
            "kind": self.kind,
            "title": self.title,
            "acceptance_criteria": list(self.acceptance_criteria),
            "depends_on": list(self.depends_on),
            "surfaces": list(self.surfaces),
            "estimate_minutes": self.estimate_minutes,
            "risk": self.risk,
            "needs_human": self.needs_human,
        }
        if self.proof:
            out["proof"] = self.proof.to_dict()
        return out


@dataclass
class Milestone:
    id: str
    title: str
    tasks: list[Task] = field(default_factory=list)

    @property
    def days(self) -> list[int]:
        return sorted({t.day for t in self.tasks})

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Milestone:
        return cls(
            id=str(d.get("id", "")),
            title=str(d.get("title", "")),
            tasks=[Task.from_dict(t) for t in d.get("tasks") or []],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "days": self.days,
            "tasks": [t.to_dict() for t in self.tasks],
        }


@dataclass
class Plan:
    project: str
    target_days: int
    profile: str
    milestones: list[Milestone] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)

    @property
    def tasks(self) -> list[Task]:
        return [t for m in self.milestones for t in m.tasks]

    def task(self, task_id: str) -> Task | None:
        return next((t for t in self.tasks if t.id == task_id), None)

    def tasks_for_day(self, day: int) -> list[Task]:
        return [t for t in self.tasks if t.day == day]

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Plan:
        if not isinstance(d, dict):
            raise PlanError(["plan is not a mapping"])
        plan = cls(
            project=str(d.get("project", "")),
            target_days=int(d.get("target_days", 0) or 0),
            profile=str(d.get("profile", "")),
            milestones=[Milestone.from_dict(m) for m in d.get("milestones") or []],
            risk_flags=[str(r) for r in d.get("risk_flags") or []],
        )
        problems = plan.problems()
        if problems:
            raise PlanError(problems)
        return plan

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": self.project,
            "target_days": self.target_days,
            "profile": self.profile,
            "milestones": [m.to_dict() for m in self.milestones],
            "risk_flags": list(self.risk_flags),
        }

    def problems(self) -> list[str]:
        """Every reason this plan cannot be executed. Empty means it can."""
        out: list[str] = []
        if not self.project:
            out.append("project is empty")
        if self.target_days < 1:
            out.append(f"target_days must be >= 1, got {self.target_days}")
        if not self.milestones:
            out.append("plan has no milestones")

        tasks = self.tasks
        if not tasks:
            out.append("plan has no tasks")
            return out

        seen: set[str] = set()
        for t in tasks:
            if not t.id:
                out.append(f"task {t.title!r} has no id")
            elif t.id in seen:
                out.append(f"duplicate task id {t.id!r}")
            seen.add(t.id)

            if not t.title:
                out.append(f"{t.id}: no title")
            if not t.acceptance_criteria:
                out.append(f"{t.id}: no acceptance_criteria — nothing downstream could check it")
            if t.kind not in KINDS:
                out.append(f"{t.id}: kind {t.kind!r} not one of {KINDS}")
            if t.risk not in RISKS:
                out.append(f"{t.id}: risk {t.risk!r} not one of {RISKS}")
            if t.day < 1 or (self.target_days and t.day > self.target_days):
                out.append(f"{t.id}: day {t.day} outside 1..{self.target_days}")

        for t in tasks:
            for dep in t.depends_on:
                target = self.task(dep)
                if target is None:
                    out.append(f"{t.id}: depends on unknown task {dep!r}")
                elif target.day > t.day:
                    out.append(
                        f"{t.id} (day {t.day}) depends on {dep} which is scheduled later "
                        f"(day {target.day})"
                    )

        out.extend(self._cycles())
        return out

    def _cycles(self) -> list[str]:
        graph = {t.id: [d for d in t.depends_on if self.task(d)] for t in self.tasks}
        state: dict[str, int] = {}  # 0 unvisited, 1 in progress, 2 done
        found: list[str] = []

        def walk(node: str, trail: list[str]) -> None:
            if state.get(node) == 1:
                cycle = trail[trail.index(node) :] + [node]
                found.append("dependency cycle: " + " -> ".join(cycle))
                return
            if state.get(node) == 2:
                return
            state[node] = 1
            for nxt in graph.get(node, []):
                walk(nxt, [*trail, node])
            state[node] = 2

        for node in graph:
            if state.get(node, 0) == 0:
                walk(node, [])
        return found


def json_schema() -> dict[str, Any]:
    """Passed to `claude --json-schema` so the Planner's output is a contract.

    Kept deliberately loose on prose fields and strict on structure: the model
    should choose the titles, not the shape.
    """
    task = {
        "type": "object",
        "required": ["id", "day", "title", "acceptance_criteria"],
        "properties": {
            "id": {"type": "string", "description": "short stable id, e.g. t1"},
            "day": {"type": "integer", "minimum": 1},
            "kind": {"type": "string", "enum": list(KINDS)},
            "title": {"type": "string"},
            "acceptance_criteria": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string"},
                "description": "checkable statements; the Reviewer diffs against these",
            },
            "depends_on": {"type": "array", "items": {"type": "string"}},
            "surfaces": {"type": "array", "items": {"type": "string"}},
            "estimate_minutes": {"type": "integer", "minimum": 5},
            "risk": {"type": "string", "enum": list(RISKS)},
            "needs_human": {"type": "boolean"},
            "proof": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string"},
                    "expect": {"type": "string"},
                },
                "required": ["kind"],
            },
        },
    }
    return {
        "type": "object",
        "required": ["project", "target_days", "milestones"],
        "properties": {
            "project": {"type": "string"},
            "target_days": {"type": "integer", "minimum": 1},
            "profile": {"type": "string"},
            "milestones": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["id", "title", "tasks"],
                    "properties": {
                        "id": {"type": "string"},
                        "title": {"type": "string"},
                        "tasks": {"type": "array", "minItems": 1, "items": task},
                    },
                },
            },
            "risk_flags": {"type": "array", "items": {"type": "string"}},
        },
    }
