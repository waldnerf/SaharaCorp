"""Runs the ground-truth SQL for every question in evals/questions.md against
data/retail.duckdb and prints question_id | sql | result, for transcription
into evals/expected.md. Never hand-type expected answers — always derive
them from this script's output.
"""
from pathlib import Path

import duckdb

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "retail.duckdb"

# Reusable net-of-returns / discount / FX line-value expression.
NET_REVENUE = "(oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_price * (1-oi.line_discount_pct) * o.fx_rate_to_eur"
NET_COST = "(oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_cost * (1-oi.line_discount_pct) * o.fx_rate_to_eur"

QUERIES: list[tuple[int, str]] = [
    (1, f"""
        SELECT o.country, ROUND(SUM({NET_REVENUE}),2) AS revenue_eur
        FROM order_items oi JOIN orders o ON o.order_id=oi.order_id
        LEFT JOIN returns r ON r.order_item_id=oi.order_item_id
        WHERE o.status='completed' GROUP BY 1 ORDER BY 1
    """),
    (2, f"""
        WITH per_order AS (
            SELECT o.order_id, o.order_date, o.status, SUM({NET_REVENUE}) AS order_revenue
            FROM order_items oi JOIN orders o ON o.order_id=oi.order_id
            LEFT JOIN returns r ON r.order_item_id=oi.order_item_id
            GROUP BY 1,2,3
        )
        SELECT
          CASE WHEN order_date BETWEEN '2025-01-01' AND '2025-03-31' THEN 'Q1-2025'
               WHEN order_date BETWEEN '2024-10-01' AND '2024-12-31' THEN 'Q4-2024' END AS quarter,
          ROUND(AVG(order_revenue),2) AS avg_order_value, COUNT(*) AS n_orders
        FROM per_order
        WHERE status='completed' AND (order_date BETWEEN '2025-01-01' AND '2025-03-31'
                                        OR order_date BETWEEN '2024-10-01' AND '2024-12-31')
        GROUP BY 1 ORDER BY 1
    """),
    (3, """
        SELECT CAST(FLOOR((EXTRACT(month FROM order_date)::INT -1)/3.0) AS INT)+1 AS quarter, COUNT(*) AS n_orders
        FROM orders WHERE status='completed' AND EXTRACT(year FROM order_date)=2025
        GROUP BY 1 ORDER BY 1
    """),
    (4, """
        SELECT COUNT(*) FROM shipments s JOIN orders o ON o.order_id=s.order_id WHERE o.country='Belgium'
    """),
    (5, """
        SELECT p.category, SUM(oi.quantity) AS total_qty
        FROM order_items oi JOIN products p ON p.product_id=oi.product_id
        GROUP BY 1 ORDER BY 2 DESC
    """),
    (6, f"""
        WITH net AS (
            SELECT o.country, o.order_date, o.status, {NET_REVENUE} AS net_revenue_eur,
                   COALESCE(r.quantity_returned,0) AS ret_qty, oi.quantity AS qty
            FROM order_items oi JOIN orders o ON o.order_id=oi.order_id
            LEFT JOIN returns r ON r.order_item_id=oi.order_item_id
        )
        SELECT
          CASE WHEN order_date BETWEEN '2025-07-01' AND '2025-09-30' THEN 'Q3-2025'
               WHEN order_date BETWEEN '2025-04-01' AND '2025-06-30' THEN 'Q2-2025' END AS quarter,
          ROUND(SUM(net_revenue_eur),2) AS net_revenue_eur,
          ROUND(SUM(ret_qty)*1.0/SUM(qty),4) AS return_rate
        FROM net WHERE country='France' AND status='completed'
          AND (order_date BETWEEN '2025-07-01' AND '2025-09-30' OR order_date BETWEEN '2025-04-01' AND '2025-06-30')
        GROUP BY 1 ORDER BY 1
    """),
    (7, f"""
        WITH order_net AS (
            SELECT o.order_id, o.customer_id, o.order_date, o.country, o.status, SUM({NET_REVENUE}) AS net_revenue_eur
            FROM order_items oi JOIN orders o ON o.order_id=oi.order_id
            LEFT JOIN returns r ON r.order_item_id=oi.order_item_id
            GROUP BY 1,2,3,4,5
        ), seg AS (
            SELECT n.order_id, h.segment
            FROM order_net n JOIN customer_segment_history h ON h.customer_id = n.customer_id
              AND h.valid_from <= n.order_date AND (h.valid_to IS NULL OR n.order_date < h.valid_to)
        )
        SELECT s.segment, ROUND(SUM(n.net_revenue_eur),2) AS revenue_eur,
               ROUND(SUM(n.net_revenue_eur) * 1.0 / SUM(SUM(n.net_revenue_eur)) OVER (), 4) AS share
        FROM order_net n JOIN seg s ON s.order_id = n.order_id
        WHERE n.country='France' AND n.status='completed' AND n.order_date BETWEEN '2025-07-01' AND '2025-09-30'
        GROUP BY 1 ORDER BY 1
    """),
    (8, f"""
        SELECT EXTRACT(year FROM o.order_date)::INT AS yr,
               CAST(FLOOR((EXTRACT(month FROM o.order_date)::INT -1)/3.0) AS INT)+1 AS q,
               ROUND(SUM({NET_REVENUE}) / NULLIF(SUM(oi.quantity - COALESCE(r.quantity_returned,0)),0), 2) AS net_revenue_per_unit
        FROM order_items oi JOIN orders o ON o.order_id=oi.order_id JOIN products p ON p.product_id=oi.product_id
        LEFT JOIN returns r ON r.order_item_id=oi.order_item_id
        WHERE o.status='completed' AND p.category='Kitchenware'
        GROUP BY 1,2 ORDER BY 1,2
    """),
    (9, f"""
        WITH order_rev AS (
            SELECT o.order_id, o.order_date, SUM({NET_REVENUE}) AS net_revenue_eur
            FROM order_items oi JOIN orders o ON o.order_id=oi.order_id
            LEFT JOIN returns r ON r.order_item_id=oi.order_item_id
            WHERE o.status='completed' GROUP BY 1,2
        ), ship_counts AS (SELECT order_id, COUNT(*) AS n_shipments FROM shipments GROUP BY 1)
        SELECT date_trunc('quarter', orv.order_date) AS quarter, COUNT(*) AS n_split_orders,
               ROUND(SUM(orv.net_revenue_eur) / SUM(sc.n_shipments), 2) AS avg_revenue_per_shipment
        FROM order_rev orv JOIN ship_counts sc ON sc.order_id = orv.order_id
        WHERE sc.n_shipments > 1
        GROUP BY 1 ORDER BY 1
    """),
    (10, """
        WITH net AS (
            SELECT o.country, EXTRACT(year FROM o.order_date)::INT AS yr,
                   CAST(FLOOR((EXTRACT(month FROM o.order_date)::INT-1)/3.0) AS INT)+1 AS q,
                   oi.quantity AS qty, COALESCE(r.quantity_returned,0) AS ret_qty
            FROM order_items oi JOIN orders o ON o.order_id=oi.order_id
            LEFT JOIN returns r ON r.order_item_id=oi.order_item_id
            WHERE o.status='completed'
        )
        SELECT country, yr, q, ROUND(SUM(ret_qty)*1.0/SUM(qty),4) AS return_rate
        FROM net GROUP BY 1,2,3 ORDER BY 4 DESC LIMIT 5
    """),
    (11, f"""
        WITH net AS (
            SELECT o.country, o.status, {NET_REVENUE} AS net_revenue_eur, {NET_COST} AS net_cost_eur, oi.line_discount_pct
            FROM order_items oi JOIN orders o ON o.order_id=oi.order_id
            LEFT JOIN returns r ON r.order_item_id=oi.order_item_id
        )
        SELECT ROUND(SUM(net_revenue_eur),2) AS revenue, ROUND(SUM(net_cost_eur),2) AS cost,
               ROUND((SUM(net_revenue_eur)-SUM(net_cost_eur))/SUM(net_revenue_eur),4) AS margin,
               ROUND(AVG(line_discount_pct),4) AS avg_discount
        FROM net WHERE country='France' AND status='completed'
    """),
    (12, f"""
        WITH order_net AS (
            SELECT o.order_id, o.customer_id, o.order_date, o.status, SUM({NET_REVENUE}) AS net_revenue_eur, SUM({NET_COST}) AS net_cost_eur
            FROM order_items oi JOIN orders o ON o.order_id=oi.order_id
            LEFT JOIN returns r ON r.order_item_id=oi.order_item_id
            WHERE o.status='completed'
            GROUP BY 1,2,3,4
        ), seg AS (
            SELECT n.order_id, h.segment FROM order_net n JOIN customer_segment_history h ON h.customer_id=n.customer_id
              AND h.valid_from <= n.order_date AND (h.valid_to IS NULL OR n.order_date < h.valid_to)
        )
        SELECT s.segment, ROUND(SUM(n.net_revenue_eur),2) AS revenue, ROUND(SUM(n.net_cost_eur),2) AS cost,
               ROUND((SUM(n.net_revenue_eur)-SUM(n.net_cost_eur))/SUM(n.net_revenue_eur),4) AS margin
        FROM order_net n JOIN seg s ON s.order_id=n.order_id GROUP BY 1 ORDER BY 1
    """),
    (13, f"""
        WITH order_agg AS (
            SELECT o.order_id, SUM({NET_REVENUE}) AS revenue, SUM({NET_COST}) AS cost
            FROM order_items oi JOIN orders o ON o.order_id=oi.order_id
            LEFT JOIN returns r ON r.order_item_id=oi.order_item_id
            WHERE o.status='completed' GROUP BY 1
        ), ship_counts AS (SELECT order_id, COUNT(*) n FROM shipments GROUP BY 1)
        SELECT CASE WHEN sc.n>=2 THEN 'multi' ELSE 'single' END AS fulfillment_type,
               ROUND((SUM(oa.revenue)-SUM(oa.cost))/SUM(oa.revenue),4) AS margin, COUNT(*) AS n_orders
        FROM order_agg oa JOIN ship_counts sc ON sc.order_id=oa.order_id GROUP BY 1 ORDER BY 1
    """),
    (14, f"""
        WITH net AS (
            SELECT o.country, EXTRACT(year FROM o.order_date)::INT AS yr, {NET_REVENUE} AS net_revenue_eur, {NET_COST} AS net_cost_eur
            FROM order_items oi JOIN orders o ON o.order_id=oi.order_id
            LEFT JOIN returns r ON r.order_item_id=oi.order_item_id
            WHERE o.status='completed'
        )
        SELECT CASE WHEN country='Switzerland' THEN 'Switzerland' ELSE 'Eurozone' END AS grp, yr,
               ROUND(SUM(net_revenue_eur),2) AS revenue,
               ROUND((SUM(net_revenue_eur)-SUM(net_cost_eur))/SUM(net_revenue_eur),4) AS margin
        FROM net GROUP BY 1,2 ORDER BY 1,2
    """),
    (15, """
        SELECT country, CASE WHEN order_date BETWEEN '2025-07-01' AND '2025-09-30' THEN 'anomaly_qtr' ELSE 'other' END AS period,
               status, COUNT(*) AS n_orders
        FROM orders WHERE country='France' GROUP BY 1,2,3 ORDER BY 2,3
    """),
    (16, f"""
        WITH net AS (
            SELECT o.customer_id, EXTRACT(year FROM o.order_date)::INT AS yr, {NET_REVENUE} AS net_revenue_eur
            FROM order_items oi JOIN orders o ON o.order_id=oi.order_id
            LEFT JOIN returns r ON r.order_item_id=oi.order_item_id
            WHERE o.status='completed'
        )
        SELECT customer_id, ROUND(SUM(net_revenue_eur),2) AS revenue_2025
        FROM net WHERE yr=2025 GROUP BY 1 ORDER BY 2 DESC LIMIT 10
    """),
    (17, f"""
        WITH net AS (
            SELECT o.customer_id, SUM({NET_REVENUE}) AS revenue, SUM({NET_COST}) AS cost
            FROM order_items oi JOIN orders o ON o.order_id=oi.order_id
            LEFT JOIN returns r ON r.order_item_id=oi.order_item_id
            WHERE o.status='completed' GROUP BY 1
        )
        SELECT COUNT(*) AS n_customers_eligible
        FROM net WHERE revenue > 0 AND (revenue*0.9 - cost) / (revenue*0.9) > 0.2
    """),
    (18, f"""
        WITH net AS (
            SELECT p.category, {NET_REVENUE} AS net_revenue_eur, {NET_COST} AS net_cost_eur
            FROM order_items oi JOIN orders o ON o.order_id=oi.order_id JOIN products p ON p.product_id=oi.product_id
            LEFT JOIN returns r ON r.order_item_id=oi.order_item_id
            WHERE o.status='completed'
        )
        SELECT category, ROUND((SUM(net_revenue_eur)-SUM(net_cost_eur))/SUM(net_revenue_eur),4) AS margin
        FROM net GROUP BY 1 ORDER BY 2 DESC
    """),
    (19, f"""
        WITH cust_stats AS (
            SELECT o.customer_id, COUNT(DISTINCT o.order_id) AS n_orders,
                   SUM({NET_REVENUE}) / COUNT(DISTINCT o.order_id) AS aov
            FROM order_items oi JOIN orders o ON o.order_id=oi.order_id
            LEFT JOIN returns r ON r.order_item_id=oi.order_item_id
            WHERE o.status='completed' GROUP BY 1
        ), current_seg AS (
            SELECT customer_id, segment FROM customer_segment_history WHERE valid_to IS NULL
        ), vip_avg AS (
            SELECT AVG(cs.n_orders) AS avg_n_orders, AVG(cs.aov) AS avg_aov
            FROM cust_stats cs JOIN current_seg s ON s.customer_id=cs.customer_id WHERE s.segment='VIP'
        )
        SELECT cs.customer_id, cs.n_orders, ROUND(cs.aov,2) AS aov,
               ROUND(ABS(cs.n_orders - va.avg_n_orders) + ABS(cs.aov - va.avg_aov)/100, 3) AS distance_to_vip_profile
        FROM cust_stats cs JOIN current_seg s ON s.customer_id=cs.customer_id, vip_avg va
        WHERE s.segment='standard'
        ORDER BY distance_to_vip_profile ASC LIMIT 10
    """),
    (20, f"""
        WITH net AS (
            SELECT o.country, EXTRACT(year FROM o.order_date)::INT AS yr, {NET_REVENUE} AS net_revenue_eur,
                   {NET_COST} AS net_cost_eur, oi.quantity AS qty, COALESCE(r.quantity_returned,0) AS ret_qty
            FROM order_items oi JOIN orders o ON o.order_id=oi.order_id
            LEFT JOIN returns r ON r.order_item_id=oi.order_item_id
            WHERE o.status='completed'
        )
        SELECT country, ROUND(SUM(net_revenue_eur),2) AS revenue,
               ROUND((SUM(net_revenue_eur)-SUM(net_cost_eur))/SUM(net_revenue_eur),4) AS margin,
               ROUND(SUM(ret_qty)*1.0/SUM(qty),4) AS return_rate
        FROM net WHERE yr=2025 GROUP BY 1 ORDER BY 1
    """),
]


def main() -> None:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        for question_id, sql in QUERIES:
            result = con.sql(sql).fetchall()
            print(f"=== Q{question_id} ===")
            print(sql.strip())
            print("--- result ---")
            for row in result:
                print(row)
            print()
    finally:
        con.close()


if __name__ == "__main__":
    main()
