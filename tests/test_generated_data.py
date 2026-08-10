"""Sanity checks on data/retail.duckdb: row counts, referential integrity, and
presence of all 5 deliberate semantic traps. Run scripts/generate_data.py first.
"""
from pathlib import Path

import duckdb
import pytest

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "retail.duckdb"


@pytest.fixture(scope="module")
def con():
    if not DB_PATH.exists():
        pytest.fail(f"{DB_PATH} does not exist — run `python -m scripts.generate_data` first")
    connection = duckdb.connect(str(DB_PATH), read_only=True)
    yield connection
    connection.close()


def _count(con, sql: str) -> int:
    return con.sql(sql).fetchone()[0]


# --- Row counts -------------------------------------------------------------

def test_row_counts_within_expected_ranges(con):
    assert 250 <= _count(con, "SELECT COUNT(*) FROM customers") <= 350
    assert 40 <= _count(con, "SELECT COUNT(*) FROM products") <= 60
    assert 1800 <= _count(con, "SELECT COUNT(*) FROM orders") <= 2200
    assert 3000 <= _count(con, "SELECT COUNT(*) FROM order_items") <= 8000
    assert _count(con, "SELECT COUNT(*) FROM returns") > 0
    assert _count(con, "SELECT COUNT(*) FROM shipments") > 0


# --- Referential integrity ---------------------------------------------------

@pytest.mark.parametrize(
    "sql",
    [
        "SELECT COUNT(*) FROM customer_segment_history h LEFT JOIN customers c USING (customer_id) WHERE c.customer_id IS NULL",
        "SELECT COUNT(*) FROM product_price_history h LEFT JOIN products p USING (product_id) WHERE p.product_id IS NULL",
        "SELECT COUNT(*) FROM orders o LEFT JOIN customers c USING (customer_id) WHERE c.customer_id IS NULL",
        "SELECT COUNT(*) FROM order_items oi LEFT JOIN orders o USING (order_id) WHERE o.order_id IS NULL",
        "SELECT COUNT(*) FROM order_items oi LEFT JOIN products p USING (product_id) WHERE p.product_id IS NULL",
        "SELECT COUNT(*) FROM returns r LEFT JOIN order_items oi USING (order_item_id) WHERE oi.order_item_id IS NULL",
        "SELECT COUNT(*) FROM shipments s LEFT JOIN orders o USING (order_id) WHERE o.order_id IS NULL",
    ],
)
def test_referential_integrity(con, sql):
    assert _count(con, sql) == 0


def test_no_orders_with_zero_order_items(con):
    sql = """
        SELECT COUNT(*) FROM orders o
        WHERE NOT EXISTS (SELECT 1 FROM order_items oi WHERE oi.order_id = o.order_id)
    """
    assert _count(con, sql) == 0


# --- Trap 1: snapshot vs. current pricing -----------------------------------

def test_trap1_at_least_one_product_has_a_price_change(con):
    sql = "SELECT COUNT(*) FROM (SELECT product_id FROM product_price_history GROUP BY product_id HAVING COUNT(*) > 1)"
    assert _count(con, sql) >= 1


def test_trap1_a_price_changed_product_has_orders_before_and_after(con):
    sql = """
        WITH changed AS (
            SELECT product_id, MIN(valid_to) AS chg_date
            FROM product_price_history WHERE valid_to IS NOT NULL GROUP BY product_id
        )
        SELECT COUNT(*) FROM changed ch
        WHERE EXISTS (
            SELECT 1 FROM order_items oi JOIN orders o ON o.order_id = oi.order_id
            WHERE oi.product_id = ch.product_id AND o.order_date < ch.chg_date
        ) AND EXISTS (
            SELECT 1 FROM order_items oi JOIN orders o ON o.order_id = oi.order_id
            WHERE oi.product_id = ch.product_id AND o.order_date >= ch.chg_date
        )
    """
    assert _count(con, sql) >= 1


# --- Trap 2: slowly-changing customer segment -------------------------------

def test_trap2_at_least_one_customer_has_a_segment_promotion(con):
    sql = "SELECT COUNT(*) FROM (SELECT customer_id FROM customer_segment_history GROUP BY customer_id HAVING COUNT(*) > 1)"
    assert _count(con, sql) >= 1


def test_trap2_a_promoted_customer_has_orders_before_and_after(con):
    sql = """
        WITH promo AS (
            SELECT customer_id, MIN(valid_to) AS promo_date
            FROM customer_segment_history WHERE valid_to IS NOT NULL GROUP BY customer_id
        )
        SELECT COUNT(*) FROM promo p
        WHERE EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = p.customer_id AND o.order_date < p.promo_date)
          AND EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = p.customer_id AND o.order_date >= p.promo_date)
    """
    assert _count(con, sql) >= 1


# --- Trap 3: partial returns / France anomaly -------------------------------

def test_trap3_france_anomaly_quarter_return_rate_exceeds_25_percent(con):
    sql = """
        SELECT SUM(COALESCE(r.quantity_returned, 0)) * 1.0 / SUM(oi.quantity)
        FROM order_items oi
        JOIN orders o ON o.order_id = oi.order_id
        LEFT JOIN returns r ON r.order_item_id = oi.order_item_id
        WHERE o.status = 'completed' AND o.country = 'France'
          AND o.order_date BETWEEN '2025-07-01' AND '2025-09-30'
    """
    rate = con.sql(sql).fetchone()[0]
    assert rate > 0.25


def test_trap3_all_other_country_quarter_combinations_stay_under_15_percent(con):
    sql = """
        WITH buckets AS (
            SELECT o.country,
                   EXTRACT(year FROM o.order_date)::INT AS yr,
                   CAST(FLOOR((EXTRACT(month FROM o.order_date)::INT - 1) / 3.0) AS INT) + 1 AS q,
                   oi.quantity, COALESCE(r.quantity_returned, 0) AS returned_qty
            FROM order_items oi
            JOIN orders o ON o.order_id = oi.order_id
            LEFT JOIN returns r ON r.order_item_id = oi.order_item_id
            WHERE o.status = 'completed'
              AND NOT (o.country = 'France' AND o.order_date BETWEEN '2025-07-01' AND '2025-09-30')
        )
        SELECT country, yr, q, SUM(returned_qty) * 1.0 / SUM(quantity) AS rate
        FROM buckets GROUP BY country, yr, q
        HAVING SUM(returned_qty) * 1.0 / SUM(quantity) >= 0.15
    """
    offending = con.sql(sql).fetchall()
    assert offending == []


def test_trap3_anomaly_orders_have_status_completed_not_cancelled(con):
    sql = """
        SELECT COUNT(*) FROM orders
        WHERE country = 'France' AND order_date BETWEEN '2025-07-01' AND '2025-09-30'
          AND status = 'completed'
    """
    assert _count(con, sql) > 0


# --- Trap 4: multi-currency ---------------------------------------------------

def test_trap4_at_least_one_chf_order_with_non_unity_fx_rate(con):
    sql = "SELECT COUNT(*) FROM orders WHERE currency = 'CHF' AND fx_rate_to_eur != 1.0"
    assert _count(con, sql) >= 1


# --- Trap 5: shipment fan-out -------------------------------------------------

def test_trap5_at_least_one_order_has_multiple_shipments(con):
    sql = "SELECT COUNT(*) FROM (SELECT order_id FROM shipments GROUP BY order_id HAVING COUNT(*) > 1)"
    assert _count(con, sql) >= 1


def test_trap5_a_multi_shipment_order_also_has_multiple_order_items(con):
    sql = """
        WITH multi_shipment AS (SELECT order_id FROM shipments GROUP BY order_id HAVING COUNT(*) >= 2),
             multi_item AS (SELECT order_id FROM order_items GROUP BY order_id HAVING COUNT(*) >= 2)
        SELECT COUNT(*) FROM multi_shipment JOIN multi_item USING (order_id)
    """
    assert _count(con, sql) >= 1


def test_trap5_naive_join_through_shipments_inflates_line_item_rows(con):
    naive = _count(con, """
        SELECT COUNT(*) FROM orders o
        JOIN shipments s ON s.order_id = o.order_id
        JOIN order_items oi ON oi.order_id = o.order_id
    """)
    correct = _count(con, "SELECT COUNT(*) FROM order_items")
    assert naive > correct
