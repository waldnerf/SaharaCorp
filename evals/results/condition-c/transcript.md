# Transcript — Sahara Retail Eval Questions

All queries follow the governed metric definitions in `semantic/retail.ossie.yaml`:
revenue/cost use `order_items.unit_price`/`unit_cost` (transaction-time price, not
`product_price_history`), are netted for `returns.quantity_returned` at the line
grain (regardless of order status), are net of `line_discount_pct`, converted to
EUR via `orders.fx_rate_to_eur`, and only `orders.status = 'completed'` counts
toward revenue/margin/order_count. `shipments` is joined only for fulfillment
questions, never on the path to `order_items`. Customer segment is looked up
point-in-time via `customer_segment_history` (`valid_from <= order_date AND
(valid_to IS NULL OR order_date < valid_to)`).

---

## Q1: What was total revenue (in EUR) for each of the four markets (France, Germany, Belgium, Switzerland) over the full data period?

```sql
SELECT o.country,
       SUM((oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_price
           * (1 - oi.line_discount_pct) * o.fx_rate_to_eur) AS revenue_eur
FROM order_items oi
JOIN orders o ON oi.order_id = o.order_id
LEFT JOIN returns r ON oi.order_item_id = r.order_item_id
WHERE o.status = 'completed'
GROUP BY o.country
ORDER BY revenue_eur DESC
```

**Answer:** Over the full data period (2024‑07‑01 to 2025‑12‑31), total net revenue in EUR was: France €290,224, Germany €258,889, Belgium €165,880, and Switzerland €158,781.

---

## Q2: What was the average order value in Q1 2025, and how does it compare to the average order value in Q4 2024?

```sql
WITH base AS (
  SELECT o.order_id,
         date_trunc('quarter', o.order_date) AS q,
         SUM((oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_price
             * (1 - oi.line_discount_pct) * o.fx_rate_to_eur) AS order_revenue
  FROM order_items oi
  JOIN orders o ON oi.order_id = o.order_id
  LEFT JOIN returns r ON oi.order_item_id = r.order_item_id
  WHERE o.status = 'completed'
    AND o.order_date >= '2024-10-01' AND o.order_date < '2025-04-01'
  GROUP BY o.order_id, date_trunc('quarter', o.order_date)
)
SELECT q, AVG(order_revenue) AS avg_order_value, COUNT(*) AS n_orders
FROM base
GROUP BY q
ORDER BY q
```

**Answer:** Average order value was €453.91 in Q4 2024 (340 orders) and €472.35 in Q1 2025 (290 orders) — Q1 2025 was about €18.44 (≈4.1%) higher than Q4 2024.

---

## Q3: How many completed orders were placed in each quarter of 2025?

```sql
SELECT date_trunc('quarter', order_date) AS q, COUNT(DISTINCT order_id) AS completed_orders
FROM orders
WHERE status = 'completed' AND order_date >= '2025-01-01' AND order_date < '2026-01-01'
GROUP BY q
ORDER BY q
```

**Answer:** Completed orders by quarter in 2025: Q1 = 290, Q2 = 308, Q3 = 315, Q4 = 362 — a steady rise through the year.

---

## Q4: How many shipments were sent to Belgium in total?

```sql
SELECT COUNT(*) AS shipments_to_belgium
FROM shipments s
JOIN orders o ON s.order_id = o.order_id
WHERE o.country = 'Belgium'
```

**Answer:** 464 shipments were sent to Belgium in total.

---

## Q5: What is the total quantity of items ordered, broken down by product category?

```sql
SELECT p.category, SUM(oi.quantity) AS total_qty_ordered
FROM order_items oi
JOIN products p ON oi.product_id = p.product_id
GROUP BY p.category
ORDER BY total_qty_ordered DESC
```

**Answer:** Total quantity ordered by category: Outdoor 2,988; Accessories 2,259; Home 1,871; Textiles 1,336; Kitchenware 970; Lighting 563.

---

## Q6: Why did net revenue in France decline in Q3 2025 compared to Q2 2025?

```sql
SELECT date_trunc('quarter', o.order_date) AS q,
       SUM((oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur) AS net_revenue,
       SUM(oi.quantity * oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur) AS gross_revenue,
       SUM(COALESCE(r.quantity_returned,0) * oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur) AS returned_value,
       SUM(COALESCE(r.quantity_returned,0)) AS qty_returned,
       SUM(oi.quantity) AS qty_ordered,
       COUNT(DISTINCT o.order_id) AS n_orders
FROM order_items oi
JOIN orders o ON oi.order_id = o.order_id
LEFT JOIN returns r ON oi.order_item_id = r.order_item_id
WHERE o.status = 'completed' AND o.country = 'France'
  AND o.order_date >= '2025-04-01' AND o.order_date < '2025-10-01'
GROUP BY q
ORDER BY q
```

**Answer:** France's net revenue fell from €54,907 in Q2 2025 to €29,998 in Q3 2025, but gross (pre-return) revenue was essentially flat (€55,482 vs €56,531) and order count actually rose (107 → 117). The decline was driven almost entirely by a spike in partial returns: only 7 of 556 units ordered were returned in Q2 (1.2%), versus 278 of 606 units returned in Q3 (45.9%) — worth €26,533 in returned value. Since returns are tracked at the line-item grain and never change `orders.status`, this anomaly is invisible to any query that looks only at order counts or order status — it only shows up when returns are netted into revenue as the governed metric does.

---

## Q7: What share of France's revenue in Q3 2025 came from customers who were VIP segment at the time of purchase?

```sql
WITH fr_q3 AS (
  SELECT oi.order_item_id, o.order_id, o.customer_id, o.order_date,
         (oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur AS net_rev
  FROM order_items oi
  JOIN orders o ON oi.order_id = o.order_id
  LEFT JOIN returns r ON oi.order_item_id = r.order_item_id
  WHERE o.status = 'completed' AND o.country = 'France'
    AND o.order_date >= '2025-07-01' AND o.order_date < '2025-10-01'
),
seg AS (
  SELECT f.*, csh.segment
  FROM fr_q3 f
  LEFT JOIN customer_segment_history csh
    ON csh.customer_id = f.customer_id
    AND csh.valid_from <= f.order_date
    AND (csh.valid_to IS NULL OR f.order_date < csh.valid_to)
)
SELECT segment, SUM(net_rev) AS revenue, SUM(net_rev) * 1.0 / SUM(SUM(net_rev)) OVER () AS share
FROM seg
GROUP BY segment
ORDER BY revenue DESC
```

**Answer:** In Q3 2025, customers who were VIP segment *at the time of their order* accounted for only about 9.8% of France's net revenue (€2,942 of €29,998); the remaining ~90.2% (€27,056) came from standard-segment customers. (This uses the customer's segment as of each order date, not their current segment.)

---

## Q8: Has average revenue per unit sold in the "Kitchenware" category changed over the data period, and why?

```sql
SELECT date_trunc('quarter', o.order_date) AS q,
       SUM((oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur) AS net_revenue,
       SUM(oi.quantity - COALESCE(r.quantity_returned,0)) AS net_units,
       SUM((oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur)
         / NULLIF(SUM(oi.quantity - COALESCE(r.quantity_returned,0)),0) AS rev_per_unit
FROM order_items oi
JOIN orders o ON oi.order_id = o.order_id
JOIN products p ON oi.product_id = p.product_id
LEFT JOIN returns r ON oi.order_item_id = r.order_item_id
WHERE o.status = 'completed' AND p.category = 'Kitchenware'
GROUP BY q
ORDER BY q
```

**Answer:** Revenue per net unit sold in Kitchenware has stayed in a fairly narrow band across the six quarters: €115.08, €112.33, €126.03, €121.66, €123.89, €113.06 (2024‑Q3 through 2025‑Q4). There is no sustained upward or downward trend — it fluctuates roughly ±6% quarter to quarter, most plausibly reflecting normal product/discount mix shifts within the category rather than a systematic pricing change (this uses `order_items.unit_price`, the price actually paid at sale, not the current catalog price).

---

## Q9: Is average revenue per shipment declining for orders that required split fulfillment (more than one shipment)?

```sql
WITH ship_counts AS (
  SELECT order_id, COUNT(*) AS n_shipments
  FROM shipments
  GROUP BY order_id
),
order_rev AS (
  SELECT o.order_id, o.order_date,
         SUM((oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur) AS net_revenue
  FROM order_items oi
  JOIN orders o ON oi.order_id = o.order_id
  LEFT JOIN returns r ON oi.order_item_id = r.order_item_id
  WHERE o.status = 'completed'
  GROUP BY o.order_id, o.order_date
)
SELECT date_trunc('quarter', orv.order_date) AS q,
       COUNT(*) AS n_split_orders,
       SUM(orv.net_revenue) AS total_net_revenue,
       SUM(sc.n_shipments) AS total_shipments,
       SUM(orv.net_revenue) / NULLIF(SUM(sc.n_shipments),0) AS avg_revenue_per_shipment
FROM order_rev orv
JOIN ship_counts sc ON orv.order_id = sc.order_id
WHERE sc.n_shipments > 1
GROUP BY q
ORDER BY q
```

(Revenue is computed from `order_items`/`orders`/`returns` only, per order; shipment counts come from a separate aggregation of `shipments` and are joined back by `order_id` — never joining `order_items` directly to `shipments`, which would fan out and inflate the sums.)

**Answer:** Average revenue per shipment for split-fulfillment orders was €219.46 (2024‑Q3), €199.74, €192.96, €183.00, then €150.48 in 2025‑Q3, before recovering to €210.01 in 2025‑Q4. So yes, there was a clear declining trend from mid‑2024 through Q3 2025 (a drop of about 31%), but it partially reversed in the most recent quarter (Q4 2025) rather than continuing to decline throughout the whole period.

---

## Q10: Which market has the highest return rate, and in which quarter does it peak?

```sql
SELECT o.country,
       SUM(COALESCE(r.quantity_returned,0)) * 1.0 / SUM(oi.quantity) AS return_rate
FROM order_items oi
JOIN orders o ON oi.order_id = o.order_id
LEFT JOIN returns r ON oi.order_item_id = r.order_item_id
GROUP BY o.country
ORDER BY return_rate DESC;

SELECT o.country, date_trunc('quarter', o.order_date) AS q,
       SUM(COALESCE(r.quantity_returned,0)) * 1.0 / SUM(oi.quantity) AS return_rate
FROM order_items oi
JOIN orders o ON oi.order_id = o.order_id
LEFT JOIN returns r ON oi.order_item_id = r.order_item_id
GROUP BY o.country, q
ORDER BY o.country, q
```

**Answer:** France has by far the highest overall return rate (10.8% of ordered quantity, vs 3.9% Switzerland, 3.3% Germany, 3.1% Belgium), and it peaks sharply in Q3 2025 at 46.6% of quantity ordered — an isolated spike versus roughly 1–5% in every other quarter for every market.

---

## Q11: Could Sahara Retail increase discounts for French customers without dropping overall margin below 20%?

```sql
-- Current France margin and average discount
SELECT o.country,
       SUM((oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur) AS revenue,
       SUM((oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_cost * (1 - oi.line_discount_pct) * o.fx_rate_to_eur) AS net_cost,
       AVG(oi.line_discount_pct) AS avg_discount_pct
FROM order_items oi
JOIN orders o ON oi.order_id = o.order_id
LEFT JOIN returns r ON oi.order_item_id = r.order_item_id
WHERE o.status = 'completed'
GROUP BY o.country;

-- Sensitivity check: recompute France margin at hypothetical uniform discount levels
WITH base AS (
  SELECT (oi.quantity - COALESCE(r.quantity_returned,0)) AS net_qty,
         oi.unit_price, oi.unit_cost, oi.line_discount_pct, o.fx_rate_to_eur
  FROM order_items oi
  JOIN orders o ON oi.order_id = o.order_id
  LEFT JOIN returns r ON oi.order_item_id = r.order_item_id
  WHERE o.status = 'completed' AND o.country = 'France'
)
SELECT
  (SUM(net_qty*unit_price*(1-line_discount_pct)*fx_rate_to_eur)-SUM(net_qty*unit_cost*(1-line_discount_pct)*fx_rate_to_eur))
    / SUM(net_qty*unit_price*(1-line_discount_pct)*fx_rate_to_eur) AS margin_actual,
  (SUM(net_qty*unit_price*(1-0.15)*fx_rate_to_eur)-SUM(net_qty*unit_cost*(1-0.15)*fx_rate_to_eur))
    / SUM(net_qty*unit_price*(1-0.15)*fx_rate_to_eur) AS margin_at_15pct_discount,
  (SUM(net_qty*unit_price*(1-0.30)*fx_rate_to_eur)-SUM(net_qty*unit_cost*(1-0.30)*fx_rate_to_eur))
    / SUM(net_qty*unit_price*(1-0.30)*fx_rate_to_eur) AS margin_at_30pct_discount
FROM base
```

**Answer:** Yes, comfortably. France's current margin is about 54.98%, far above the 20% floor, at an average discount of ~4.9%. Moreover, because `order_items.unit_cost` is discounted by the same `line_discount_pct` factor as `unit_price` in this data (i.e., cost and price move together), the margin percentage is essentially invariant to the discount level itself — recomputing margin at a hypothetical uniform 15% or 30% discount still yields ~54.97%. So the real constraint on France's margin isn't the discount rate; discounts could be raised substantially (well beyond typical retail ranges) without mechanically breaching the 20% floor, as long as the underlying unit_cost/unit_price mix doesn't change.

---

## Q12: Is the VIP customer segment actually more profitable (higher margin) than standard customers?

```sql
WITH lines AS (
  SELECT oi.order_item_id, o.order_id, o.customer_id, o.order_date, o.fx_rate_to_eur,
         (oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur AS net_rev,
         (oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_cost * (1 - oi.line_discount_pct) * o.fx_rate_to_eur AS net_cost
  FROM order_items oi
  JOIN orders o ON oi.order_id = o.order_id
  LEFT JOIN returns r ON oi.order_item_id = r.order_item_id
  WHERE o.status = 'completed'
),
seg AS (
  SELECT l.*, csh.segment
  FROM lines l
  LEFT JOIN customer_segment_history csh
    ON csh.customer_id = l.customer_id
    AND csh.valid_from <= l.order_date
    AND (csh.valid_to IS NULL OR l.order_date < csh.valid_to)
)
SELECT segment, SUM(net_rev) AS revenue, SUM(net_cost) AS cost,
       (SUM(net_rev) - SUM(net_cost)) / NULLIF(SUM(net_rev),0) AS margin
FROM seg
GROUP BY segment
ORDER BY margin DESC
```

**Answer:** No — VIP and standard customers have essentially identical margins: standard 54.88% vs VIP 54.54% (using each customer's segment as of the order date). If anything, VIP margin is marginally lower, not higher. VIP status doesn't confer a measurable profitability edge in this data.

---

## Q13: Are orders that required split fulfillment (2+ shipments) more or less profitable on average than single-shipment orders?

```sql
WITH ship_counts AS (
  SELECT order_id, COUNT(*) AS n_shipments FROM shipments GROUP BY order_id
),
order_fin AS (
  SELECT o.order_id,
         SUM((oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur) AS net_rev,
         SUM((oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_cost * (1 - oi.line_discount_pct) * o.fx_rate_to_eur) AS net_cost
  FROM order_items oi
  JOIN orders o ON oi.order_id = o.order_id
  LEFT JOIN returns r ON oi.order_item_id = r.order_item_id
  WHERE o.status = 'completed'
  GROUP BY o.order_id
)
SELECT CASE WHEN COALESCE(sc.n_shipments,1) > 1 THEN 'split (2+)' ELSE 'single' END AS fulfillment_type,
       COUNT(*) AS n_orders,
       SUM(of.net_rev) AS total_revenue,
       AVG(of.net_rev) AS avg_revenue_per_order,
       (SUM(of.net_rev)-SUM(of.net_cost)) / NULLIF(SUM(of.net_rev),0) AS margin
FROM order_fin of
LEFT JOIN ship_counts sc ON of.order_id = sc.order_id
GROUP BY fulfillment_type
```

(Order-level revenue/cost are computed purely from `order_items`/`orders`/`returns`; shipment counts are joined in afterward by `order_id`, so no fan-out occurs.)

**Answer:** Split-fulfillment orders (287 orders) are slightly *more* profitable on average than single-shipment orders (1,644 orders): €482.31 avg revenue/order and 55.02% margin vs €447.29 avg revenue/order and 54.83% margin. The difference is small but consistent — split orders tend to be somewhat larger and marginally higher margin, not less profitable.

---

## Q14: Based on revenue and margin trends, does it look worthwhile for Sahara Retail to expand its Swiss operations relative to the Eurozone markets?

```sql
WITH lines AS (
  SELECT o.country, date_trunc('quarter', o.order_date) AS q,
         (oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur AS net_rev,
         (oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_cost * (1 - oi.line_discount_pct) * o.fx_rate_to_eur AS net_cost
  FROM order_items oi
  JOIN orders o ON oi.order_id = o.order_id
  LEFT JOIN returns r ON oi.order_item_id = r.order_item_id
  WHERE o.status = 'completed'
)
SELECT country, q, SUM(net_rev) AS revenue, (SUM(net_rev)-SUM(net_cost))/NULLIF(SUM(net_rev),0) AS margin
FROM lines
GROUP BY country, q
ORDER BY country, q
```

**Answer:** Not obviously. Switzerland's quarterly revenue (€22.9k–€30.5k, converted to EUR via `fx_rate_to_eur`) is roughly on par with Belgium and noticeably smaller than France or Germany, with no clear outsized growth trend versus the eurozone markets over the six quarters. Margins are essentially identical across all four markets (~54–56%, no material spread). Since Switzerland shows neither superior margin nor a distinctly stronger growth trajectory than the Eurozone markets — only comparable performance at smaller scale — the trend data alone doesn't make a strong case for prioritizing Swiss expansion over investing in the larger, equally profitable France/Germany markets (note France's headline revenue is currently depressed by the Q3 2025 return anomaly, not a real demand issue).

---

## Q15: Would the elevated return activity in France in Q3 2025 be visible if we only looked at cancelled orders?

```sql
SELECT country, date_trunc('quarter', order_date) AS q,
       COUNT(*) FILTER (WHERE status='cancelled') AS n_cancelled,
       COUNT(*) AS n_total,
       COUNT(*) FILTER (WHERE status='cancelled') * 1.0 / COUNT(*) AS cancel_rate
FROM orders
WHERE country = 'France'
GROUP BY country, q
ORDER BY q
```

**Answer:** No. France's cancellation rate in Q3 2025 was 1.7% (2 of 119 orders) — actually the *lowest* of any quarter in the dataset (other quarters ranged 2.1%–5.5%). The Q3 2025 return spike is invisible in `orders.status`, because partial returns are tracked separately at the order-item grain and never flip a completed order to cancelled. A manager looking only at cancelled-order counts would see nothing unusual and miss the anomaly entirely.

---

## Q16: Identify the top 10 customers by net revenue across all four markets in 2025.

```sql
SELECT o.customer_id, c.country,
       SUM((oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur) AS net_revenue_2025
FROM order_items oi
JOIN orders o ON oi.order_id = o.order_id
JOIN customers c ON o.customer_id = c.customer_id
LEFT JOIN returns r ON oi.order_item_id = r.order_item_id
WHERE o.status = 'completed' AND o.order_date >= '2025-01-01' AND o.order_date < '2026-01-01'
GROUP BY o.customer_id, c.country
ORDER BY net_revenue_2025 DESC
LIMIT 10
```

**Answer:** The top 10 customers by 2025 net revenue: customer 61 (Switzerland, €7,674), 176 (Germany, €6,089), 227 (Germany, €5,674), 185 (France, €5,090), 121 (France, €5,034), 244 (Germany, €4,793), 277 (Germany, €4,755), 106 (France, €4,707), 60 (Germany, €4,621), and 170 (France, €4,508).

---

## Q17: Identify which customers could be offered a 10% discount while keeping margin above 20%, across all markets.

```sql
WITH cust AS (
  SELECT o.customer_id,
         SUM((oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur) AS revenue,
         SUM((oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_cost * (1 - oi.line_discount_pct) * o.fx_rate_to_eur) AS cost
  FROM order_items oi
  JOIN orders o ON oi.order_id = o.order_id
  LEFT JOIN returns r ON oi.order_item_id = r.order_item_id
  WHERE o.status = 'completed'
  GROUP BY o.customer_id
),
calc AS (
  SELECT customer_id, revenue, cost,
         (revenue - cost)/NULLIF(revenue,0) AS current_margin,
         (revenue*0.9 - cost) / NULLIF(revenue*0.9,0) AS margin_after_10pct_discount
  FROM cust
  WHERE revenue > 0
)
SELECT COUNT(*) AS total_customers,
       COUNT(*) FILTER (WHERE margin_after_10pct_discount > 0.20) AS eligible_customers
FROM calc
```

**Answer:** All 300 customers with completed-order revenue would remain above 20% margin after a 10% price discount (assuming cost per unit is unaffected by the discount). This follows from the fact that current margins cluster tightly around ~55% for essentially every customer — a straight 10% price cut still leaves roughly ~50% margin, comfortably above the 20% floor, so eligibility isn't a differentiator here; every customer qualifies.

---

## Q18: Rank product categories by margin, using the prices customers actually paid rather than current catalog prices.

```sql
SELECT p.category,
       SUM((oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur) AS revenue,
       SUM((oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_cost * (1 - oi.line_discount_pct) * o.fx_rate_to_eur) AS cost,
       (SUM((oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur)
        - SUM((oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_cost * (1 - oi.line_discount_pct) * o.fx_rate_to_eur))
        / NULLIF(SUM((oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur),0) AS margin
FROM order_items oi
JOIN orders o ON oi.order_id = o.order_id
JOIN products p ON oi.product_id = p.product_id
LEFT JOIN returns r ON oi.order_item_id = r.order_item_id
WHERE o.status = 'completed'
GROUP BY p.category
ORDER BY margin DESC
```

**Answer:** Ranked by margin (using the actual transaction-time `unit_price`/`unit_cost`, not catalog prices): Kitchenware 56.7% (highest), Accessories 55.5%, Outdoor 54.8%, Textiles 54.4%, Home 54.2%, and Lighting 50.2% (lowest).

---

## Q19: If VIP-segment customers are more profitable, which standard customers look most similar to VIP customers on their purchase history, and could be considered for promotion?

```sql
-- Profile of current VIP vs standard customers
WITH lines AS (
  SELECT oi.order_item_id, o.order_id, o.customer_id, o.order_date,
         (oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur AS net_rev
  FROM order_items oi
  JOIN orders o ON oi.order_id = o.order_id
  LEFT JOIN returns r ON oi.order_item_id = r.order_item_id
  WHERE o.status = 'completed'
),
cust_agg AS (
  SELECT customer_id, SUM(net_rev) AS total_revenue, COUNT(DISTINCT order_id) AS n_orders,
         SUM(net_rev)/COUNT(DISTINCT order_id) AS avg_order_value
  FROM lines
  GROUP BY customer_id
),
cust_current_seg AS (
  SELECT customer_id, segment FROM customer_segment_history WHERE valid_to IS NULL
),
vip_stats AS (
  SELECT AVG(ca.total_revenue) AS vip_avg_rev, AVG(ca.avg_order_value) AS vip_avg_aov
  FROM cust_agg ca JOIN cust_current_seg ccs ON ca.customer_id = ccs.customer_id
  WHERE ccs.segment = 'VIP'
)
SELECT ca.customer_id, ca.total_revenue, ca.n_orders, ca.avg_order_value
FROM cust_agg ca
JOIN cust_current_seg ccs ON ca.customer_id = ccs.customer_id
CROSS JOIN vip_stats vs
WHERE ccs.segment = 'standard'
  AND ca.total_revenue >= vs.vip_avg_rev
  AND ca.avg_order_value >= vs.vip_avg_aov
ORDER BY ca.total_revenue DESC
LIMIT 20
```

**Answer:** As established in Q12, VIP customers are not actually more profitable than standard customers on margin (~54.5% VIP vs ~54.9% standard) — so the premise doesn't hold on margin. On purchase-volume metrics, though, the current 32 VIP customers average €2,562 lifetime net revenue and €427 average order value, while several standard customers already exceed both figures: the top matches are customers 61, 176, 242, 244, 185, 227, 121, 294, 45, 69, 29, 60, 272, 150, 206, 117, 287, 67, 73, and 295 (all with total revenue ≥ €5,000 and AOV ≥ VIP average). These are the standard customers most similar to VIP purchase behavior and worth considering for promotion — but promotion should be framed around retention/purchase volume rather than margin, since VIP status itself doesn't carry a margin premium in this data.

---

## Q20: Build a market-by-market summary of revenue, margin, and return rate for 2025 that a regional manager could use to decide which market to prioritize fixing first.

```sql
WITH lines AS (
  SELECT o.country,
         (oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur AS net_rev,
         (oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_cost * (1 - oi.line_discount_pct) * o.fx_rate_to_eur AS net_cost,
         oi.quantity AS qty, COALESCE(r.quantity_returned,0) AS qty_ret,
         o.status
  FROM order_items oi
  JOIN orders o ON oi.order_id = o.order_id
  LEFT JOIN returns r ON oi.order_item_id = r.order_item_id
  WHERE o.order_date >= '2025-01-01' AND o.order_date < '2026-01-01'
)
SELECT country,
       SUM(net_rev) FILTER (WHERE status='completed') AS revenue,
       (SUM(net_rev) FILTER (WHERE status='completed') - SUM(net_cost) FILTER (WHERE status='completed'))
         / NULLIF(SUM(net_rev) FILTER (WHERE status='completed'),0) AS margin,
       SUM(qty_ret) * 1.0 / NULLIF(SUM(qty),0) AS return_rate
FROM lines
GROUP BY country
ORDER BY revenue DESC
```

**Answer:** 2025 market summary (revenue = net EUR revenue on completed orders; margin = net margin %; return rate = % of ordered quantity returned, all orders):

| Market | Revenue (EUR) | Margin | Return rate |
|---|---|---|---|
| France | €193,383 | 55.0% | 14.3% |
| Germany | €168,155 | 55.1% | 3.4% |
| Belgium | €101,911 | 54.5% | 3.5% |
| Switzerland | €100,682 | 54.8% | 3.6% |

All four markets have essentially the same margin (~54.5–55.1%), so margin isn't a differentiator. France is both the largest market by revenue and the clear outlier on returns — its 14.3% return rate is roughly 4x every other market, driven almost entirely by the Q3 2025 spike (46.6% that quarter alone). **France should be prioritized first**: it's the biggest revenue base, so recovering the abnormal returns there recaptures the most euros, and the return anomaly (not margin or overall demand) is the specific, fixable problem — it doesn't show up in cancelled-order counts, so it needs to be tracked via the returns table directly.
