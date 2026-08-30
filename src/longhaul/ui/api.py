"""The HTTP surface the interface reads.

Deliberately a plain read-only JSON API rather than anything clever: it is served
by stdlib `http.server`, consumed by a Next.js app that is statically exported
and bundled into this package, and it has to stay simple enough that the
zero-dependency fallback page can use the same endpoints.

Nothing here writes. Actions — approve, skip, retry — belong to a shared command
layer that both this and the Telegram bot will call, and that does not exist yet.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..core import registry, transcript
from ..core import state as state_io
from ..schema.plan import Plan, PlanError
from ..schema.state import DONE, FAILED, HALTED, PARKED
from .data import build


def _load(root: Path) -> tuple[Plan | None, Any, list[dict], str | None]:
    path = root / ".longhaul" / "plan.yaml"
    if not path.is_file():
        return None, state_io.load(root), [], f"no plan at {path}"
    try:
        plan = Plan.from_dict(yaml.safe_load(path.read_text(encoding="utf-8")))
    except PlanError as exc:
        return None, state_io.load(root), [], (
            f"plan.yaml has {len(exc.problems)} problem(s): {exc.problems[0]}"
        )
    except (OSError, yaml.YAMLError) as exc:
        return None, state_io.load(root), [], f"plan.yaml could not be read: {exc}"
    return plan, state_io.load(root), state_io.read_ledger(root), None


def projects() -> dict[str, Any]:
    """Everything the home screen needs, without opening every transcript."""
    out = []
    for project in registry.load().projects:
        row: dict[str, Any] = {
            **project.to_dict(),
            "exists": project.exists,
            "status": "ok",
        }
        if not project.exists:
            row["status"] = "missing"
            out.append(row)
            continue

        plan, state, ledger, problem = _load(project.path)
        if plan is None:
            row["status"] = "unplanned"
            row["problem"] = problem
            out.append(row)
            continue

        counts = state.counts()
        counts["pending"] += sum(1 for t in plan.tasks if t.id not in state.tasks)
        row.update(
            {
                "title": plan.project,
                "profile": plan.profile,
                "target_days": plan.target_days,
                "tasks": len(plan.tasks),
                "counts": counts,
                "days_done": counts[DONE],
                "total_cost_usd": state.total_cost_usd,
                "updated_at": state.updated_at,
                "runs": len(ledger),
                "needs_you": counts[PARKED] + counts[HALTED] + counts[FAILED],
            }
        )
        out.append(row)
    return {"projects": out}


def project_data(project_id: str, embed: bool = False) -> dict[str, Any]:
    project = registry.load().get(project_id)
    if project is None:
        return {"error": f"no project called '{project_id}'"}
    if not project.exists:
        return {"error": f"{project.path} no longer has a .longhaul/ directory"}

    plan, state, ledger, problem = _load(project.path)
    if plan is None:
        return {"error": problem, "project_id": project_id, "path": str(project.path)}

    payload = build(plan, state, ledger, root=project.path, embed=embed, live=True)
    payload["project_id"] = project_id
    payload["path"] = str(project.path)
    payload["transcripts"] = transcript.index(project.path)
    return payload


def project_transcript(project_id: str, relative: str) -> dict[str, Any]:
    """One stored run, read back as a conversation."""
    project = registry.load().get(project_id)
    if project is None:
        return {"error": f"no project called '{project_id}'"}

    runs_root = (project.path / ".longhaul" / "runs").resolve()
    try:
        path = (project.path / relative).resolve()
        # `resolve()` collapses `..`; this is what stops a crafted id reading
        # anything outside the runs directory.
        path.relative_to(runs_root)
    except (ValueError, OSError):
        return {"error": "not found"}
    if not path.is_file():
        return {"error": "not found"}

    body = transcript.read(path).to_dict()
    body["id"] = relative
    return body


def summary(project_id: str) -> dict[str, Any]:
    payload = project_data(project_id)
    if "error" in payload:
        return payload
    return {
        "project": payload["project"],
        "target_days": payload["target_days"],
        "tasks": payload["tasks_total"],
        "counts": payload["counts"],
        "total_cost_usd": payload["total_cost_usd"],
    }


#: Statuses that mean a human has to look. Used by the home screen's badge.
ATTENTION = (PARKED, HALTED, FAILED)
