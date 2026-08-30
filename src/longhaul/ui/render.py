"""`.longhaul/` → the interface.

One page, two ways to deliver it. `longhaul report` embeds the data as JSON in
the document, so a single file is fully interactive with no network at all —
filters, sorting and every view work offline, from a CI artefact, from an email
attachment. `longhaul ui` serves the same shell and refreshes the data over SSE.

The rendering lives in `assets/app.js` rather than here on purpose: one renderer
for both surfaces. Two would drift, and then one of them would lie.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

from ..schema.plan import Plan
from ..schema.state import DONE, FAILED, HALTED, IN_PROGRESS, PARKED, SKIPPED, State
from .data import build

ASSETS = Path(__file__).parent / "assets"
BUCKETS = (DONE, FAILED, PARKED, HALTED, IN_PROGRESS, SKIPPED, "pending")


def _asset(name: str) -> str:
    return (ASSETS / name).read_text(encoding="utf-8")


def shell(title: str, payload: dict | None) -> str:
    """The document. `payload` embedded means it works with no server at all."""
    embedded = ""
    if payload is not None:
        # </script> inside JSON would end the block early; escaping the slash is
        # the standard defence and keeps it valid JSON.
        blob = json.dumps(payload).replace("</", "<\\/")
        embedded = f'<script type="application/json" id="longhaul-data">{blob}</script>'

    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="robots" content="noindex">\n'
        f"<title>{html.escape(title)} — Longhaul</title>\n"
        f"<style>{_asset('app.css')}</style>\n"
        '<div class="app">'
        '<nav class="sidebar" id="sidebar"></nav>'
        "<div>"
        '<header class="topbar" id="topbar"></header>'
        '<main id="main"></main>'
        "</div>"
        "</div>\n"
        f"{embedded}\n"
        f"<script>{_asset('app.js')}</script>\n"
    )


def render(
    plan: Plan,
    state: State,
    ledger: list[dict] | None = None,
    live: bool = False,
    root: Path | None = None,
    embed: bool = True,
) -> str:
    payload = build(plan, state, ledger, root=root, embed=embed, live=live)
    return shell(plan.project, None if live else payload)


def write(
    plan: Plan,
    state: State,
    out: Path,
    ledger: list[dict] | None = None,
    root: Path | None = None,
) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(plan, state, ledger, root=root, embed=True), encoding="utf-8")
    return out


def summary(plan: Plan, state: State) -> dict:
    """The headline numbers, for callers that want data rather than markup."""
    counts = state.counts()
    counts["pending"] += sum(1 for t in plan.tasks if t.id not in state.tasks)
    return {
        "project": plan.project,
        "target_days": plan.target_days,
        "tasks": len(plan.tasks),
        **{k: counts[k] for k in BUCKETS},
        "total_cost_usd": state.total_cost_usd,
    }


def to_json(plan: Plan, state: State) -> str:
    return json.dumps(summary(plan, state), indent=2)
