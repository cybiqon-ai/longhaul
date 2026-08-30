"""Everything the interface needs, as one JSON payload.

The same payload drives both surfaces: the live server serves it from `/api/data`
and refreshes over SSE, and `longhaul report` embeds it in the page. That is what
lets a single-file report stay fully interactive with no network — the filters,
sorting and views all work off data already in the document.

One payload, one renderer, two delivery mechanisms. Two implementations would
drift, and then one of them would lie.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from ..schema.plan import Plan
from ..schema.state import DONE, FAILED, HALTED, IN_PROGRESS, PARKED, SKIPPED, State
from .gallery import collect
from .redact import redact

BUCKETS = (DONE, FAILED, PARKED, HALTED, IN_PROGRESS, SKIPPED, "pending")


def _milestone_of(plan: Plan, task_id: str) -> str:
    for milestone in plan.milestones:
        if any(t.id == task_id for t in milestone.tasks):
            return milestone.title
    return ""


def build(
    plan: Plan,
    state: State,
    ledger: list[dict] | None = None,
    root: Path | None = None,
    embed: bool = True,
    live: bool = False,
) -> dict[str, Any]:
    ledger = ledger or []

    counts = state.counts()
    counts["pending"] = sum(1 for t in plan.tasks if t.id not in state.tasks) + counts["pending"]

    tasks = []
    for task in sorted(plan.tasks, key=lambda t: (t.day, t.id)):
        ts = state.tasks.get(task.id)
        tasks.append(
            {
                "id": task.id,
                "day": task.day,
                "title": task.title,
                "kind": task.kind,
                "risk": task.risk,
                "needs_human": task.needs_human,
                "surfaces": task.surfaces,
                "estimate_minutes": task.estimate_minutes,
                "criteria": task.acceptance_criteria,
                "depends_on": task.depends_on,
                "milestone": _milestone_of(plan, task.id),
                "proof_expect": task.proof.expect if task.proof else "",
                # state
                "status": ts.status if ts else "pending",
                "attempts": ts.attempts if ts else 0,
                "cost_usd": round(ts.cost_usd, 4) if ts else 0.0,
                "branch": ts.branch if ts else None,
                "commit_sha": (ts.commit_sha[:12] if ts and ts.commit_sha else None),
                "pr_number": ts.pr_number if ts else None,
                "pr_url": ts.pr_url if ts else None,
                "ci_run_id": ts.ci_run_id if ts else None,
                "started_at": ts.started_at if ts else None,
                "finished_at": ts.finished_at if ts else None,
                "last_error": redact(ts.last_error) if ts else "",
                "findings": [redact(f) for f in (ts.findings if ts else [])],
                "proof_kind": ts.proof_kind if ts else None,
                "proof_detail": redact(ts.proof_detail) if ts else "",
                "proof_artifacts": list(ts.proof_artifacts) if ts else [],
            }
        )

    by_task = {t["id"]: t for t in tasks}
    runs = []
    for entry in ledger:
        task_id = entry.get("task", "")
        runs.append(
            {
                "at": entry.get("at", ""),
                "task": task_id,
                "day": by_task.get(task_id, {}).get("day"),
                "title": by_task.get(task_id, {}).get("title", ""),
                "role": entry.get("role", ""),
                "attempt": entry.get("attempt", 1),
                "session_id": entry.get("session_id"),
                "cost_usd": round(float(entry.get("cost_usd") or 0), 4),
                "duration_s": round(float(entry.get("duration_s") or 0), 1),
                "ok": bool(entry.get("ok")),
            }
        )
    runs.sort(key=lambda r: r["at"], reverse=True)

    # Per-day series for the chart strip. Every day in range, so gaps show as
    # gaps rather than being silently closed up.
    cost_by_day: dict[int, float] = defaultdict(float)
    runs_by_day: dict[int, int] = defaultdict(int)
    for task in tasks:
        cost_by_day[task["day"]] += task["cost_usd"]
    for run in runs:
        if run["day"]:
            runs_by_day[run["day"]] += 1
    series = [
        {
            "day": day,
            "cost_usd": round(cost_by_day.get(day, 0.0), 4),
            "runs": runs_by_day.get(day, 0),
            "statuses": [t["status"] for t in tasks if t["day"] == day],
        }
        for day in range(1, plan.target_days + 1)
    ]

    gallery = collect(root, embed=embed) if root else None
    proof = (
        [
            {
                "day": a.day,
                "task": a.task_id,
                "name": a.path.name,
                "href": a.href,
                "src": a.data_uri or a.href,
                "is_image": a.is_image,
                "size": a.size,
            }
            for a in gallery.artefacts
        ]
        if gallery
        else []
    )

    done = counts[DONE]
    return {
        "project": plan.project,
        "profile": plan.profile,
        "target_days": plan.target_days,
        "updated_at": state.updated_at,
        "live": live,
        "counts": {k: counts[k] for k in BUCKETS},
        "tasks_total": len(tasks),
        "days_done": done,
        "total_cost_usd": state.total_cost_usd,
        "risk_flags": plan.risk_flags,
        "milestones": [
            {"id": m.id, "title": m.title, "days": m.days} for m in plan.milestones
        ],
        "tasks": tasks,
        "runs": runs,
        "series": series,
        "proof": proof,
        "proof_linked": gallery.linked if gallery else 0,
    }
