"""Estimating a cost the CLI never reported.

A timed-out design task that had run thirty minutes — roughly $2.76 at list
price — was recorded as $0.00, and every ceiling in the supervisor was blind to
it. A labelled estimate is honest; zero is not.
"""

from longhaul.driver import pricing


def turn(mid, model="claude-opus-5", **usage):
    return {"type": "assistant", "message": {"id": mid, "model": model, "usage": usage}}


def test_an_empty_stream_costs_nothing():
    assert pricing.estimate([]) == 0.0


def test_a_turn_is_priced_by_its_model():
    events = [turn("m1", input_tokens=1_000_000)]
    assert pricing.estimate(events) == 5.0  # opus input


def test_cache_reads_and_writes_use_their_multipliers():
    events = [turn("m1", cache_read_input_tokens=1_000_000,
                   cache_creation_input_tokens=1_000_000)]
    assert pricing.estimate(events) == round(5 * 0.1 + 5 * 1.25, 4)


def test_a_turn_repeated_across_content_blocks_is_counted_once():
    """The CLI emits one assistant event per content block, each carrying the
    same usage. Summing them directly overcounts a turn several times."""
    same = turn("m1", input_tokens=1_000_000)
    assert pricing.estimate([same, same, same]) == 5.0


def test_distinct_turns_add_up():
    assert pricing.estimate([turn("m1", input_tokens=1_000_000),
                             turn("m2", input_tokens=1_000_000)]) == 10.0


def test_an_unknown_model_is_priced_high_so_a_ceiling_stops_early():
    events = [turn("m1", model="some-future-model", input_tokens=1_000_000)]
    assert pricing.estimate(events) == pricing.FALLBACK[0]


def test_dated_model_ids_resolve_by_prefix():
    assert pricing.price_for("claude-haiku-4-5-20251001") == (1.0, 5.0)
    assert pricing.price_for("claude-sonnet-5") == (2.0, 10.0)


def test_non_assistant_events_are_ignored():
    events = [{"type": "system", "subtype": "init"}, {"type": "user"},
              turn("m1", input_tokens=1_000_000)]
    assert pricing.estimate(events) == 5.0
