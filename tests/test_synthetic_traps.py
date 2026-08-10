"""Unit tests for scripts/lib/synthetic_traps.py against a toy, non-retail domain.

Uses generic "widget"/"owner" entities on purpose: if any of these tests need
a retail concept to pass, the library has leaked domain coupling.
"""
from datetime import date
from random import Random

import pytest

from scripts.lib.synthetic_traps import (
    generate_child_reversal,
    generate_fanout_fact,
    generate_fx_rates,
    generate_scd2_history,
    snapshot_as_of,
)

START = date(2024, 1, 1)
END = date(2024, 12, 31)


def test_scd2_history_windows_are_gapless_and_non_overlapping():
    rng = Random(1)
    widget_ids = list(range(200))

    def initial_value_fn(_rng):
        return {"state": "A"}

    def transition_value_fn(_rng, _previous):
        return {"state": "B"}

    rows = generate_scd2_history(widget_ids, initial_value_fn, transition_value_fn, 0.4, START, END, rng)

    by_widget: dict[int, list[dict]] = {}
    for row in rows:
        by_widget.setdefault(row["entity_id"], []).append(row)

    for widget_id, widget_rows in by_widget.items():
        widget_rows.sort(key=lambda r: r["valid_from"])
        assert widget_rows[0]["valid_from"] == START
        assert widget_rows[-1]["valid_to"] is None
        for prev, nxt in zip(widget_rows, widget_rows[1:]):
            assert prev["valid_to"] == nxt["valid_from"]

    assert any(len(v) == 2 for v in by_widget.values()), "expected at least one widget to transition"
    assert any(len(v) == 1 for v in by_widget.values()), "expected at least one widget to never transition"


def test_snapshot_as_of_resolves_correctly_around_a_transition():
    rng = Random(2)
    widget_ids = list(range(500))

    def initial_value_fn(_rng):
        return {"state": "A"}

    def transition_value_fn(_rng, _previous):
        return {"state": "B"}

    rows = generate_scd2_history(widget_ids, initial_value_fn, transition_value_fn, 0.5, START, END, rng)

    by_widget: dict[int, list[dict]] = {}
    for row in rows:
        by_widget.setdefault(row["entity_id"], []).append(row)
    transitioned = next(wid for wid, r in by_widget.items() if len(r) == 2)
    transition_row = min(by_widget[transitioned], key=lambda r: r["valid_from"])
    transition_date = transition_row["valid_to"]

    day_before = snapshot_as_of(rows, transitioned, transition_date - __import__("datetime").timedelta(days=1))
    day_of = snapshot_as_of(rows, transitioned, transition_date)

    assert day_before["state"] == "A"
    assert day_of["state"] == "B"


def test_child_reversal_anomaly_subset_elevates_rate_only_for_target():
    rng = Random(3)
    parents = [{"id": i, "group": "target" if i < 300 else "other"} for i in range(3000)]

    def reversal_amount_fn(_rng, _parent):
        return {"amount": 1}

    rows = generate_child_reversal(
        parents,
        reversal_rate=0.05,
        reversal_amount_fn=reversal_amount_fn,
        rng=rng,
        anomaly_subset=lambda p: p["group"] == "target",
        anomaly_rate=0.4,
    )

    reversed_ids = {r["parent_id"] for r in rows}
    target_ids = {p["id"] for p in parents if p["group"] == "target"}
    other_ids = {p["id"] for p in parents if p["group"] == "other"}

    target_rate = len(reversed_ids & target_ids) / len(target_ids)
    other_rate = len(reversed_ids & other_ids) / len(other_ids)

    assert target_rate > 0.3
    assert other_rate < 0.1
    assert target_rate > 3 * other_rate


def test_fanout_fact_respects_multi_rate_within_tolerance():
    rng = Random(4)
    parent_ids = list(range(2000))

    rows = generate_fanout_fact(parent_ids, min_children=1, max_children=3, multi_rate=0.2, rng=rng)

    counts: dict[int, int] = {}
    for row in rows:
        counts[row["parent_id"]] = counts.get(row["parent_id"], 0) + 1

    multi_child_fraction = sum(1 for c in counts.values() if c >= 2) / len(counts)
    assert 0.14 <= multi_child_fraction <= 0.26
    assert all(c >= 1 for c in counts.values())
    assert max(counts.values()) <= 3


def test_fx_rates_base_currency_is_always_one_and_noise_is_bounded():
    rng = Random(5)
    dates = [date(2024, 1, 1), date(2024, 6, 1)]

    rates = generate_fx_rates({"CHF": 0.96}, base_currency="EUR", dates=dates, rng=rng, noise_pct=0.02)

    for d in dates:
        assert rates[("EUR", d)] == 1.0
        assert 0.94 <= rates[("CHF", d)] <= 0.98


def test_snapshot_as_of_raises_when_no_row_covers_the_date():
    rows = [{"entity_id": 1, "valid_from": date(2024, 6, 1), "valid_to": None, "state": "A"}]
    with pytest.raises(ValueError):
        snapshot_as_of(rows, 1, date(2024, 1, 1))
