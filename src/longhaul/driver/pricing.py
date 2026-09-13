"""Estimate what a run cost when the CLI never said.

The CLI reports `total_cost_usd` only in its final result event. A call that
times out, or dies, never emits one — and recording that as $0.00 makes a real
spend invisible to every ceiling in the supervisor. A timed-out design task
that had run thirty minutes was logged as free.

So when the figure is missing it is estimated from the usage the stream already
carried, and **flagged as an estimate** everywhere it appears. List prices go
stale; a stale, labelled estimate is still far closer to the truth than zero.

The estimate is a lower bound: usage on streamed assistant events is recorded at
the start of each turn, so output tokens are undercounted. Cache reads dominate a
long agent run anyway, and those are counted properly.
"""

from __future__ import annotations

from typing import Any

#: (input, output) in USD per million tokens. Cache reads bill at 0.1x input and
#: cache writes at 1.25x. Matched by prefix, so dated variants resolve.
PRICES: tuple[tuple[str, float, float], ...] = (
    ("claude-fable", 10.0, 50.0),
    ("claude-mythos", 10.0, 50.0),
    ("claude-opus", 5.0, 25.0),
    ("claude-sonnet-5", 2.0, 10.0),
    ("claude-sonnet", 3.0, 15.0),
    ("claude-haiku", 1.0, 5.0),
)
#: Unknown model: price it as the most expensive, so a ceiling errs towards
#: stopping early rather than spending blind.
FALLBACK = (10.0, 50.0)


def price_for(model: str | None) -> tuple[float, float]:
    for prefix, inp, out in PRICES:
        if model and model.startswith(prefix):
            return inp, out
    return FALLBACK


def estimate(events: list[dict[str, Any]]) -> float:
    """Cost of the API turns visible in a partial stream, deduplicated by message.

    The CLI repeats a message's usage on every content block it emits, so
    summing events directly would count one turn several times.
    """
    turns: dict[str, tuple[str | None, dict[str, Any]]] = {}
    for event in events:
        if event.get("type") != "assistant":
            continue
        message = event.get("message") or {}
        key = message.get("id") or f"anon-{len(turns)}"
        turns[key] = (message.get("model"), message.get("usage") or {})

    total = 0.0
    for model, usage in turns.values():
        inp, out = price_for(model)
        total += (
            int(usage.get("input_tokens") or 0) * inp
            + int(usage.get("output_tokens") or 0) * out
            + int(usage.get("cache_read_input_tokens") or 0) * inp * 0.1
            + int(usage.get("cache_creation_input_tokens") or 0) * inp * 1.25
        ) / 1_000_000
    return round(total, 4)
