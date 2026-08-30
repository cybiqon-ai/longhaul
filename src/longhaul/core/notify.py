"""What gets said, and to whom.

The message body is built here so every backend says the same thing, and so the
one rule that matters is enforced in one place: **report a count, not a status.**
"Day 4 done" is a status. "Day 4/14 · 1 done · 2 parked · $0.51" is a count, and
it is the difference between a digest anyone reads and one nobody does.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..integrations import telegram
from ..schema.config import Config
from ..schema.plan import Plan
from ..schema.state import DONE, FAILED, HALTED, PARKED, State


@dataclass(frozen=True)
class Delivery:
    attempted: bool
    ok: bool
    detail: str


def digest(plan: Plan, state: State, headline: str) -> str:
    counts = state.counts()
    counts["pending"] += sum(1 for t in plan.tasks if t.id not in state.tasks)
    done = counts[DONE]
    lines = [
        f"<b>{telegram.escape(plan.project)}</b>",
        telegram.escape(headline),
        "",
        f"day {done}/{plan.target_days} · "
        f"{done} done · {counts[FAILED]} failed · {counts[PARKED]} parked · "
        f"{counts[HALTED]} halted · {counts['pending']} to go",
        f"spent ${state.total_cost_usd:.2f}",
    ]

    waiting = [t for t in state.tasks.values() if t.status in (PARKED, HALTED)]
    if waiting:
        lines += ["", "<b>needs you</b>"]
        for ts in waiting[:5]:
            reason = (ts.last_error or "").splitlines()[0][:90]
            lines.append(f"· {telegram.escape(ts.id)} — {telegram.escape(reason)}")

    prs = [t for t in state.tasks.values() if t.pr_url]
    if prs:
        lines += ["", "<b>open PRs</b>"]
        lines += [f"· #{t.pr_number} {t.pr_url}" for t in prs[-3:]]
    return "\n".join(lines)


def send(config: Config, plan: Plan, state: State, headline: str, *, failure: bool) -> Delivery:
    """Deliver the digest. Never raises — see integrations/telegram.py."""
    backend = (config.notify.backend or "none").lower()
    if backend == "none":
        return Delivery(False, False, "no notifier configured")
    if not failure and not config.notify.on_success:
        return Delivery(False, False, "success notifications are off")
    if backend != "telegram":
        return Delivery(False, False, f"unknown notifier backend {backend!r}")

    result = telegram.send(digest(plan, state, headline))
    if result.ok:
        return Delivery(True, True, f"telegram message {result.message_id}")
    return Delivery(True, False, f"telegram failed: {result.error}")
