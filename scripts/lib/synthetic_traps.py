"""Domain-agnostic synthetic-data generators for the 5 semantic-layer traps.

No table, column, or entity name from any specific business domain (retail
or otherwise) may appear in this file. Callers pass in entity/parent ids
and value-generator callbacks; this module only knows about generic
entities, parents, children, and validity windows.
"""
from __future__ import annotations

from datetime import date, timedelta
from random import Random
from typing import Callable, Iterable, Optional


def _random_date_between(rng: Random, start: date, end: date) -> date:
    delta_days = (end - start).days
    if delta_days <= 1:
        return start
    offset = rng.randrange(1, delta_days)
    return start + timedelta(days=offset)


def generate_scd2_history(
    entity_ids: Iterable,
    initial_value_fn: Callable[[Random], dict],
    transition_value_fn: Callable[[Random, dict], dict],
    transition_rate: float,
    start_date: date,
    end_date: date,
    rng: Random,
) -> list[dict]:
    """Type-2 slowly-changing history: each entity gets 1 row, or 2 rows if it transitions.

    Returns rows shaped {entity_id, valid_from, valid_to, **attrs}, valid_to=None
    meaning "still current". initial_value_fn(rng) -> attrs; transition_value_fn(rng, previous_attrs)
    -> new attrs, called only for entities selected to transition.
    """
    rows: list[dict] = []
    for entity_id in entity_ids:
        initial_attrs = initial_value_fn(rng)
        if rng.random() < transition_rate:
            transition_date = _random_date_between(rng, start_date, end_date)
            rows.append({"entity_id": entity_id, "valid_from": start_date, "valid_to": transition_date, **initial_attrs})
            new_attrs = transition_value_fn(rng, initial_attrs)
            rows.append({"entity_id": entity_id, "valid_from": transition_date, "valid_to": None, **new_attrs})
        else:
            rows.append({"entity_id": entity_id, "valid_from": start_date, "valid_to": None, **initial_attrs})
    return rows


def snapshot_as_of(history_rows: list[dict], entity_id, as_of_date: date) -> dict:
    """Point-in-time lookup: the history row valid for entity_id on as_of_date."""
    for row in history_rows:
        if row["entity_id"] != entity_id:
            continue
        if row["valid_from"] <= as_of_date and (row["valid_to"] is None or as_of_date < row["valid_to"]):
            return row
    raise ValueError(f"No history row covers entity_id={entity_id!r} as_of={as_of_date!r}")


def generate_child_reversal(
    parent_rows: list[dict],
    reversal_rate: float,
    reversal_amount_fn: Callable[[Random, dict], dict],
    rng: Random,
    anomaly_subset: Optional[Callable[[dict], bool]] = None,
    anomaly_rate: Optional[float] = None,
) -> list[dict]:
    """Partial, child-grain reversal rows against a parent fact.

    Each parent_row (must contain an "id" key) independently gets a reversal
    row with probability reversal_rate, or anomaly_rate if anomaly_subset(parent_row)
    is True. reversal_amount_fn(rng, parent_row) -> attrs for the reversal row.
    """
    rows: list[dict] = []
    for parent in parent_rows:
        rate = reversal_rate
        if anomaly_subset is not None and anomaly_rate is not None and anomaly_subset(parent):
            rate = anomaly_rate
        if rng.random() < rate:
            attrs = reversal_amount_fn(rng, parent)
            rows.append({"parent_id": parent["id"], **attrs})
    return rows


def generate_fx_rates(
    currency_base_rates: dict[str, float],
    base_currency: str,
    dates: Iterable[date],
    rng: Random,
    noise_pct: float = 0.02,
) -> dict[tuple[str, date], float]:
    """FX rate to base_currency per (currency, date), with small realistic noise.

    currency_base_rates maps each non-base currency to its approximate rate
    to base_currency; base_currency itself always rates 1.0.
    """
    rates: dict[tuple[str, date], float] = {}
    for d in dates:
        rates[(base_currency, d)] = 1.0
        for currency, base_rate in currency_base_rates.items():
            noise = 1 + rng.uniform(-noise_pct, noise_pct)
            rates[(currency, d)] = round(base_rate * noise, 4)
    return rates


def generate_fanout_fact(
    parent_ids: Iterable,
    min_children: int,
    max_children: int,
    multi_rate: float,
    rng: Random,
) -> list[dict]:
    """Auxiliary 1:N fact where a multi_rate fraction of parents get 2+ children.

    Returns rows shaped {parent_id, child_id}, with child_id sequential across
    the whole result set.
    """
    rows: list[dict] = []
    child_id = 1
    for parent_id in parent_ids:
        if rng.random() < multi_rate:
            n_children = rng.randint(max(2, min_children + 1), max(2, max_children))
        else:
            n_children = min_children
        for _ in range(n_children):
            rows.append({"parent_id": parent_id, "child_id": child_id})
            child_id += 1
    return rows
