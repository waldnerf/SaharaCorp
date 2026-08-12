"""Retail recipe: generates data/retail.duckdb for the Context Layer Lab.

Table/column names, row counts, and business parameters live here. The
actual SCD/reversal/FX/fan-out mechanics are in scripts/lib/synthetic_traps.py
and must not be reimplemented in this file.
"""
from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

import duckdb
from faker import Faker

from scripts.lib.synthetic_traps import (
    generate_child_reversal,
    generate_fanout_fact,
    generate_fx_rates,
    generate_scd2_history,
    snapshot_as_of,
)

SEED = 42

LAUNCH_DATE = date(2024, 1, 1)
DATA_START = date(2024, 7, 1)
DATA_END = date(2025, 12, 31)
ANOMALY_START = date(2025, 7, 1)
ANOMALY_END = date(2025, 9, 30)
ANOMALY_COUNTRY = "France"

N_CUSTOMERS = 300
N_PRODUCTS = 50
N_ORDERS = 2000

MARKETS = [
    ("France", "EUR", 0.35),
    ("Germany", "EUR", 0.30),
    ("Belgium", "EUR", 0.20),
    ("Switzerland", "CHF", 0.15),
]
CATEGORIES = ["Home", "Kitchenware", "Outdoor", "Accessories", "Lighting", "Textiles"]

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "retail.duckdb"


def _days_between(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def generate_customers(rng: random.Random, fake: Faker) -> list[dict]:
    countries = [m[0] for m in MARKETS]
    weights = [m[2] for m in MARKETS]
    rows = []
    for customer_id in range(1, N_CUSTOMERS + 1):
        country = rng.choices(countries, weights=weights, k=1)[0]
        signup_date = LAUNCH_DATE + timedelta(days=rng.randrange(0, (date(2024, 6, 30) - LAUNCH_DATE).days))
        rows.append(
            {
                "customer_id": customer_id,
                "name": fake.name(),
                "email": fake.unique.email(),
                "country": country,
                "signup_date": signup_date,
            }
        )
    return rows


def generate_customer_segments(rng: random.Random, customers: list[dict]) -> list[dict]:
    def initial_value_fn(_rng):
        return {"segment": "standard"}

    def transition_value_fn(_rng, _previous):
        return {"segment": "VIP"}

    customer_ids = [c["customer_id"] for c in customers]
    return generate_scd2_history(
        customer_ids, initial_value_fn, transition_value_fn, transition_rate=0.15,
        start_date=LAUNCH_DATE, end_date=DATA_END, rng=rng,
    )


def generate_products(rng: random.Random, fake: Faker) -> list[dict]:
    rows = []
    for product_id in range(1, N_PRODUCTS + 1):
        category = rng.choice(CATEGORIES)
        rows.append(
            {
                "product_id": product_id,
                "name": f"{fake.word().capitalize()} {category[:-1] if category.endswith('s') else category}",
                "category": category,
                "subcategory": f"{category} - {rng.choice(['Standard', 'Premium', 'Basic'])}",
            }
        )
    return rows


def generate_product_pricing(rng: random.Random, products: list[dict]) -> list[dict]:
    def initial_value_fn(_rng):
        unit_cost = round(_rng.uniform(5, 80), 2)
        unit_price = round(unit_cost * _rng.uniform(1.8, 2.6), 2)
        return {"unit_price": unit_price, "unit_cost": unit_cost}

    def transition_value_fn(_rng, previous):
        shift = _rng.uniform(1.08, 1.18)
        return {"unit_price": round(previous["unit_price"] * shift, 2), "unit_cost": round(previous["unit_cost"] * shift, 2)}

    product_ids = [p["product_id"] for p in products]
    return generate_scd2_history(
        product_ids, initial_value_fn, transition_value_fn, transition_rate=0.2,
        start_date=LAUNCH_DATE, end_date=DATA_END, rng=rng,
    )


def generate_orders(rng: random.Random, customers: list[dict], fx_rates: dict) -> list[dict]:
    rows = []
    n_days = (DATA_END - DATA_START).days
    for order_id in range(1, N_ORDERS + 1):
        customer = rng.choice(customers)
        order_date = DATA_START + timedelta(days=rng.randrange(0, n_days + 1))
        if order_date < customer["signup_date"]:
            order_date = customer["signup_date"] + timedelta(days=rng.randrange(0, 30))
        currency = "CHF" if customer["country"] == "Switzerland" else "EUR"
        status = "cancelled" if rng.random() < 0.04 else "completed"
        rows.append(
            {
                "order_id": order_id,
                "customer_id": customer["customer_id"],
                "order_date": order_date,
                "country": customer["country"],
                "currency": currency,
                "fx_rate_to_eur": fx_rates[(currency, order_date)],
                "status": status,
            }
        )
    return rows


def generate_order_items(rng: random.Random, orders: list[dict], products: list[dict], price_history: list[dict]) -> list[dict]:
    rows = []
    order_item_id = 1
    for order in orders:
        n_items = rng.randint(1, 4)
        chosen_products = rng.sample(products, k=min(n_items, len(products)))
        for product in chosen_products:
            snapshot = snapshot_as_of(price_history, product["product_id"], order["order_date"])
            quantity = rng.randint(1, 3)
            line_discount_pct = rng.choice([0, 0, 0, 0.05, 0.10, 0.15])
            rows.append(
                {
                    "id": order_item_id,
                    "order_item_id": order_item_id,
                    "order_id": order["order_id"],
                    "product_id": product["product_id"],
                    "quantity": quantity,
                    "unit_price": snapshot["unit_price"],
                    "unit_cost": snapshot["unit_cost"],
                    "line_discount_pct": line_discount_pct,
                    "country": order["country"],
                    "order_date": order["order_date"],
                }
            )
            order_item_id += 1
    return rows


def generate_returns(rng: random.Random, order_items: list[dict]) -> list[dict]:
    def is_anomaly(item: dict) -> bool:
        return item["country"] == ANOMALY_COUNTRY and ANOMALY_START <= item["order_date"] <= ANOMALY_END

    def reversal_amount_fn(_rng, parent):
        quantity_returned = _rng.randint(1, parent["quantity"])
        reason = _rng.choice(["damaged_in_transit", "wrong_item", "changed_mind", "fulfillment_delay"])
        return {
            "quantity_returned": quantity_returned,
            "return_date": parent["order_date"] + timedelta(days=_rng.randint(3, 21)),
            "reason": reason,
        }

    reversal_rows = generate_child_reversal(
        order_items, reversal_rate=0.045, reversal_amount_fn=reversal_amount_fn, rng=rng,
        anomaly_subset=is_anomaly, anomaly_rate=0.6,
    )
    return [
        {
            "return_id": i,
            "order_item_id": r["parent_id"],
            "return_date": r["return_date"],
            "quantity_returned": r["quantity_returned"],
            "reason": r["reason"],
        }
        for i, r in enumerate(reversal_rows, start=1)
    ]


def generate_shipments(rng: random.Random, orders: list[dict]) -> list[dict]:
    order_ids = [o["order_id"] for o in orders]
    rows = generate_fanout_fact(order_ids, min_children=1, max_children=3, multi_rate=0.22, rng=rng)
    return [
        {
            "shipment_id": r["child_id"],
            "order_id": r["parent_id"],
            "ship_date": None,
            "carrier": rng.choice(["PostEU", "SwissPost", "ExpressLog"]),
            "tracking_number": f"{rng.choice(['PE','SP','EL'])}{rng.randint(10**8, 10**9 - 1)}",
            "weight_kg": round(rng.uniform(0.3, 12.0), 2),
        }
        for r in rows
    ]


def build_database(con: duckdb.DuckDBPyConnection, tables: dict[str, list[dict]]) -> None:
    con.execute("""
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY, name VARCHAR, email VARCHAR,
            country VARCHAR, signup_date DATE
        )
    """)
    con.execute("""
        CREATE TABLE customer_segments (
            customer_id INTEGER, segment VARCHAR, valid_from DATE, valid_to DATE
        )
    """)
    con.execute("""
        CREATE TABLE products (
            product_id INTEGER PRIMARY KEY, name VARCHAR, category VARCHAR, subcategory VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE product_pricing (
            product_id INTEGER, unit_price DECIMAL(10,2), unit_cost DECIMAL(10,2),
            valid_from DATE, valid_to DATE
        )
    """)
    con.execute("""
        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY, customer_id INTEGER, order_date DATE, country VARCHAR,
            currency VARCHAR, fx_rate_to_eur DECIMAL(10,4), status VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE order_items (
            order_item_id INTEGER PRIMARY KEY, order_id INTEGER, product_id INTEGER,
            quantity INTEGER, unit_price DECIMAL(10,2), unit_cost DECIMAL(10,2),
            line_discount_pct DECIMAL(5,2)
        )
    """)
    con.execute("""
        CREATE TABLE returns (
            return_id INTEGER PRIMARY KEY, order_item_id INTEGER, return_date DATE,
            quantity_returned INTEGER, reason VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE shipments (
            shipment_id INTEGER PRIMARY KEY, order_id INTEGER, ship_date DATE, carrier VARCHAR,
            tracking_number VARCHAR, weight_kg DECIMAL(6,2)
        )
    """)

    con.executemany(
        "INSERT INTO customers VALUES (?, ?, ?, ?, ?)",
        [(c["customer_id"], c["name"], c["email"], c["country"], c["signup_date"]) for c in tables["customers"]],
    )
    con.executemany(
        "INSERT INTO customer_segments VALUES (?, ?, ?, ?)",
        [(r["entity_id"], r["segment"], r["valid_from"], r["valid_to"]) for r in tables["customer_segments"]],
    )
    con.executemany(
        "INSERT INTO products VALUES (?, ?, ?, ?)",
        [(p["product_id"], p["name"], p["category"], p["subcategory"]) for p in tables["products"]],
    )
    con.executemany(
        "INSERT INTO product_pricing VALUES (?, ?, ?, ?, ?)",
        [(r["entity_id"], r["unit_price"], r["unit_cost"], r["valid_from"], r["valid_to"]) for r in tables["product_pricing"]],
    )
    con.executemany(
        "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (o["order_id"], o["customer_id"], o["order_date"], o["country"], o["currency"], o["fx_rate_to_eur"], o["status"])
            for o in tables["orders"]
        ],
    )
    con.executemany(
        "INSERT INTO order_items VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (i["order_item_id"], i["order_id"], i["product_id"], i["quantity"], i["unit_price"], i["unit_cost"], i["line_discount_pct"])
            for i in tables["order_items"]
        ],
    )
    con.executemany(
        "INSERT INTO returns VALUES (?, ?, ?, ?, ?)",
        [(r["return_id"], r["order_item_id"], r["return_date"], r["quantity_returned"], r["reason"]) for r in tables["returns"]],
    )
    con.executemany(
        "INSERT INTO shipments VALUES (?, ?, ?, ?, ?, ?)",
        [
            (s["shipment_id"], s["order_id"], s["ship_date"], s["carrier"], s["tracking_number"], s["weight_kg"])
            for s in tables["shipments"]
        ],
    )


def main() -> None:
    fake = Faker()
    Faker.seed(SEED)
    rng = random.Random(SEED)

    customers = generate_customers(rng, fake)
    customer_segments = generate_customer_segments(rng, customers)
    products = generate_products(rng, fake)
    product_pricing = generate_product_pricing(rng, products)

    order_dates = _days_between(DATA_START, DATA_END)
    fx_rates = generate_fx_rates({"CHF": 0.96}, base_currency="EUR", dates=order_dates, rng=rng)

    orders = generate_orders(rng, customers, fx_rates)
    order_items = generate_order_items(rng, orders, products, product_pricing)
    returns = generate_returns(rng, order_items)
    shipments = generate_shipments(rng, orders)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    con = duckdb.connect(str(DB_PATH))
    try:
        build_database(
            con,
            {
                "customers": customers,
                "customer_segments": customer_segments,
                "products": products,
                "product_pricing": product_pricing,
                "orders": orders,
                "order_items": order_items,
                "returns": returns,
                "shipments": shipments,
            },
        )
    finally:
        con.close()

    print(f"Wrote {DB_PATH} — {len(customers)} customers, {len(orders)} orders, "
          f"{len(order_items)} order_items, {len(returns)} returns, {len(shipments)} shipments")


if __name__ == "__main__":
    main()
