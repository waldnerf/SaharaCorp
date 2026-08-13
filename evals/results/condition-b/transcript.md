## Q1: What was total revenue (in EUR) for each of the four markets (France, Germany, Belgium, Switzerland) over the full data period?

```sql
SELECT o.country AS market,
  ROUND(SUM(oi.unit_price * oi.quantity * (1 - oi.line_discount_pct) * o.fx_rate_to_eur), 2) AS revenue_eur
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.status = 'completed'
GROUP BY 1
ORDER BY 1;
```

**Answer:** Belgium: €170,895.14; France: €325,547.80; Germany: €267,834.12; Switzerland: €165,332.25 (Swiss orders are placed in CHF and converted to EUR using each order's daily fx_rate_to_eur).

---

## Q2: What was the average order value in Q1 2025, and how does it compare to the average order value in Q4 2024?

```sql
WITH order_val AS (
  SELECT o.order_id, date_trunc('quarter', o.order_date) AS q,
    SUM(oi.unit_price * oi.quantity * (1 - oi.line_discount_pct) * o.fx_rate_to_eur) AS order_value_eur
  FROM orders o
  JOIN order_items oi ON oi.order_id = o.order_id
  WHERE o.status = 'completed'
    AND o.order_date >= '2024-10-01' AND o.order_date < '2025-04-01'
  GROUP BY 1, 2
)
SELECT q, COUNT(*) AS n_orders, ROUND(AVG(order_value_eur), 2) AS avg_order_value_eur
FROM order_val
GROUP BY 1
ORDER BY 1;
```

**Answer:** Average order value was €490.88 in Q1 2025 vs €474.87 in Q4 2024 — an increase of about €16.01 (+3.4%). (Order value uses each order line's actual transaction price, i.e. `order_items.unit_price`, not the current product catalog price, since catalog prices have changed over time for some products.)

---

## Q3: How many completed orders were placed in each quarter of 2025?

```sql
SELECT date_trunc('quarter', order_date) AS quarter, COUNT(*) AS n_completed_orders
FROM orders
WHERE status = 'completed'
  AND order_date >= '2025-01-01' AND order_date <= '2025-12-31'
GROUP BY 1
ORDER BY 1;
```

**Answer:** Q1 2025: 290; Q2 2025: 308; Q3 2025: 315; Q4 2025: 362 completed orders.

---

## Q4: How many shipments were sent to Belgium in total?

```sql
SELECT COUNT(*) AS n_shipments
FROM shipments s
JOIN orders o ON o.order_id = s.order_id
WHERE o.country = 'Belgium';
```

**Answer:** 484 shipments were sent to Belgium.

---

## Q5: What is the total quantity of items ordered, broken down by product category?

```sql
SELECT p.category, SUM(oi.quantity) AS total_quantity
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id
JOIN products p ON p.product_id = oi.product_id
WHERE o.status = 'completed'
GROUP BY 1
ORDER BY 2 DESC;
```

**Answer:** Outdoor: 2,886; Accessories: 2,188; Home: 1,794; Textiles: 1,293; Kitchenware: 940; Lighting: 550 units (completed orders only).

---

## Q6: Why did net revenue in France decline in Q3 2025 compared to Q2 2025?

```sql
WITH line AS (
  SELECT o.order_id, date_trunc('quarter', o.order_date) AS q,
    oi.order_item_id,
    oi.unit_price * oi.quantity * (1 - oi.line_discount_pct) * o.fx_rate_to_eur AS gross_eur,
    oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur AS unit_net_price
  FROM orders o
  JOIN order_items oi ON oi.order_id = o.order_id
  WHERE o.status = 'completed' AND o.country = 'France'
),
ret AS (
  SELECT order_item_id, SUM(quantity_returned) AS qty_ret
  FROM returns
  GROUP BY 1
)
SELECT l.q,
  ROUND(SUM(l.gross_eur), 2) AS gross_rev,
  ROUND(SUM(COALESCE(r.qty_ret, 0) * l.unit_net_price), 2) AS returned_amt,
  ROUND(SUM(l.gross_eur) - SUM(COALESCE(r.qty_ret, 0) * l.unit_net_price), 2) AS net_rev
FROM line l
LEFT JOIN ret r ON r.order_item_id = l.order_item_id
WHERE l.q IN ('2025-04-01', '2025-07-01')
GROUP BY 1
ORDER BY 1;
```

**Answer:** Net revenue fell from €54,907.00 in Q2 2025 to €29,997.81 in Q3 2025 (-45%). Gross (pre-return) revenue was actually slightly *higher* in Q3 2025 (€56,530.76) than in Q2 2025 (€55,482.22), so the decline is not caused by fewer or smaller sales — it is entirely caused by a sharp spike in returns: returned value jumped from €575.21 in Q2 2025 to €26,532.95 in Q3 2025 (159 return events vs. a handful in other quarters), wiping out nearly half of gross revenue that quarter.

---

## Q7: What share of France's revenue in Q3 2025 came from customers who were VIP segment at the time of purchase?

```sql
WITH line AS (
  SELECT o.order_id, o.customer_id, o.order_date,
    oi.unit_price * oi.quantity * (1 - oi.line_discount_pct) * o.fx_rate_to_eur AS gross_eur
  FROM orders o
  JOIN order_items oi ON oi.order_id = o.order_id
  WHERE o.status = 'completed' AND o.country = 'France'
    AND o.order_date >= '2025-07-01' AND o.order_date < '2025-10-01'
),
seg AS (
  SELECT l.order_id, l.gross_eur,
    (SELECT cs.segment FROM customer_segments cs
     WHERE cs.customer_id = l.customer_id
       AND l.order_date >= cs.valid_from
       AND (cs.valid_to IS NULL OR l.order_date < cs.valid_to)
     LIMIT 1) AS segment_at_purchase
  FROM line l
)
SELECT segment_at_purchase,
  ROUND(SUM(gross_eur), 2) AS rev,
  ROUND(100.0 * SUM(gross_eur) / SUM(SUM(gross_eur)) OVER (), 2) AS pct_of_total
FROM seg
GROUP BY 1;
```

**Answer:** Customers who were VIP **at the time of purchase** accounted for €4,112.16, or about 7.3% of France's Q3 2025 revenue (€52,418.60 / 92.7% came from customers who were standard at the time of purchase). This uses each customer's segment as it stood on the order date (a customer's segment can change over time), not their current segment.

---

## Q8: Has average revenue per unit sold in the "Kitchenware" category changed over the data period, and why?

```sql
SELECT date_trunc('quarter', o.order_date) AS q,
  ROUND(SUM(oi.unit_price * oi.quantity * (1 - oi.line_discount_pct) * o.fx_rate_to_eur) / SUM(oi.quantity), 2) AS avg_rev_per_unit_eur,
  SUM(oi.quantity) AS units
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
JOIN products p ON p.product_id = oi.product_id
WHERE o.status = 'completed' AND p.category = 'Kitchenware'
GROUP BY 1
ORDER BY 1;
```

**Answer:** No sustained change — average revenue per unit sold (computed from the actual transaction price on each order line, not the current catalog price) bounces around a narrow band: €114.13, €114.07, €127.00, €121.22, €122.84, €113.03 by quarter from 2024-Q3 through 2025-Q4, ending close to where it started. Two of the six Kitchenware products did get catalog price increases mid-period (product 10: €142.05→€165.63 in Aug 2024; product 19: €25.25→€27.56 in May 2025), but those increases don't show up as a durable rise in category-level revenue-per-unit — the quarter-to-quarter movement looks like normal fluctuation from product mix and discounting rather than a genuine pricing trend.

---

## Q9: Is average revenue per shipment declining for orders that required split fulfillment (more than one shipment)?

```sql
WITH order_rev AS (
  SELECT o.order_id, date_trunc('quarter', o.order_date) AS q,
    SUM(oi.unit_price * oi.quantity * (1 - oi.line_discount_pct) * o.fx_rate_to_eur) AS order_rev_eur
  FROM orders o
  JOIN order_items oi ON oi.order_id = o.order_id
  WHERE o.status = 'completed'
  GROUP BY 1, 2
),
ship_counts AS (
  SELECT order_id, COUNT(*) AS n_ships FROM shipments GROUP BY 1
)
SELECT r.q,
  ROUND(AVG(r.order_rev_eur / s.n_ships), 2) AS avg_rev_per_shipment_eur,
  COUNT(*) AS n_split_orders
FROM order_rev r
JOIN ship_counts s ON s.order_id = r.order_id
WHERE s.n_ships > 1
GROUP BY 1
ORDER BY 1;
```

**Answer:** No — there is no sustained decline. Average revenue per shipment for split-fulfillment orders (order revenue divided by that order's own shipment count, so multi-shipment orders aren't double-counted) moves: €234.87 → €201.09 → €189.99 → €223.97 → €228.19 → €211.14 from 2024-Q3 through 2025-Q4. It dipped in late 2024/early 2025 and recovered through mid-2025, ending only modestly below the starting quarter — a fluctuation, not a trend.

---

## Q10: Which market has the highest return rate, and in which quarter does it peak?

```sql
WITH items AS (
  SELECT o.order_id, o.country, date_trunc('quarter', o.order_date) AS q, oi.order_item_id, oi.quantity
  FROM orders o
  JOIN order_items oi ON oi.order_id = o.order_id
  WHERE o.status = 'completed'
),
ret AS (
  SELECT order_item_id, SUM(quantity_returned) AS qty_ret FROM returns GROUP BY 1
)
SELECT i.country, i.q,
  SUM(i.quantity) AS qty_ordered,
  SUM(COALESCE(r.qty_ret, 0)) AS qty_returned,
  ROUND(100.0 * SUM(COALESCE(r.qty_ret, 0)) / SUM(i.quantity), 2) AS return_rate_pct
FROM items i
LEFT JOIN ret r ON r.order_item_id = i.order_item_id
GROUP BY 1, 2
ORDER BY 1, 2;
```

**Answer:** France has the highest return rate overall (10.86% of units ordered over the full period, vs. 3.76% Switzerland, 3.45% Germany, 2.93% Belgium), driven almost entirely by a spike to 45.87% in Q3 2025 (compared with 1–4% in every other quarter for France).

---

## Q11: Could Sahara Retail increase discounts for French customers without dropping overall margin below 20%?

```sql
WITH line AS (
  SELECT oi.unit_price * oi.quantity * o.fx_rate_to_eur AS list_rev,
         oi.unit_cost * oi.quantity * o.fx_rate_to_eur AS cost
  FROM orders o
  JOIN order_items oi ON oi.order_id = o.order_id
  WHERE o.status = 'completed' AND o.country = 'France'
)
SELECT ROUND(SUM(cost) / SUM(list_rev), 4) AS cost_to_list_ratio,
       ROUND(1 - (SUM(cost) / SUM(list_rev)) / 0.8, 4) AS breakeven_discount_for_20pct_margin
FROM line;
```

**Answer:** Yes, there is substantial headroom. France's current average line-level discount is only about 4.9%, and current overall margin (net of returns) is 52.74%. Cost is roughly 45% of list price, so margin only reaches the 20% floor once the average discount reaches about 43.8% (breakeven: margin = 20% when `(1 - discount) = cost_ratio / 0.8 ≈ 0.5623`, i.e. discount ≈ 43.8%). Discounts could be increased well beyond current levels — into the 30–40% range — before overall margin in France would risk dropping below 20%.

---

## Q12: Is the VIP customer segment actually more profitable (higher margin) than standard customers?

```sql
WITH line AS (
  SELECT o.order_id, o.customer_id, o.order_date, oi.order_item_id,
    oi.unit_price * oi.quantity * (1 - oi.line_discount_pct) * o.fx_rate_to_eur AS net_rev,
    oi.unit_cost * oi.quantity * o.fx_rate_to_eur AS net_cost,
    oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur AS unit_net_price,
    oi.unit_cost * o.fx_rate_to_eur AS unit_net_cost
  FROM orders o
  JOIN order_items oi ON oi.order_id = o.order_id
  WHERE o.status = 'completed'
),
seg AS (
  SELECT l.*,
    (SELECT cs.segment FROM customer_segments cs
     WHERE cs.customer_id = l.customer_id AND l.order_date >= cs.valid_from
       AND (cs.valid_to IS NULL OR l.order_date < cs.valid_to) LIMIT 1) AS segment_at_purchase
  FROM line l
),
ret AS (SELECT order_item_id, SUM(quantity_returned) AS qty_ret FROM returns GROUP BY 1)
SELECT s.segment_at_purchase,
  ROUND(SUM(s.net_rev) - SUM(COALESCE(r.qty_ret, 0) * s.unit_net_price), 2) AS net_revenue,
  ROUND(SUM(s.net_cost) - SUM(COALESCE(r.qty_ret, 0) * s.unit_net_cost), 2) AS net_cost,
  ROUND(100.0 * ((SUM(s.net_rev) - SUM(COALESCE(r.qty_ret, 0) * s.unit_net_price)) - (SUM(s.net_cost) - SUM(COALESCE(r.qty_ret, 0) * s.unit_net_cost))) / (SUM(s.net_rev) - SUM(COALESCE(r.qty_ret, 0) * s.unit_net_price)), 2) AS margin_pct
FROM seg s
LEFT JOIN ret r ON r.order_item_id = s.order_item_id
GROUP BY 1;
```

**Answer:** No, not meaningfully. Using each customer's segment as it stood at the time of each purchase, VIP-segment purchases carried a 52.03% margin vs. 52.53% for standard-segment purchases — essentially the same, with standard customers marginally higher. There is no evidence that VIP customers are more profitable on a margin basis.

---

## Q13: Are orders that required split fulfillment (2+ shipments) more or less profitable on average than single-shipment orders?

```sql
WITH order_fin AS (
  SELECT o.order_id,
    SUM(oi.unit_price * oi.quantity * (1 - oi.line_discount_pct) * o.fx_rate_to_eur) AS gross_rev,
    SUM(oi.unit_cost * oi.quantity * o.fx_rate_to_eur) AS gross_cost
  FROM orders o
  JOIN order_items oi ON oi.order_id = o.order_id
  WHERE o.status = 'completed'
  GROUP BY 1
),
ret_by_order AS (
  SELECT oi.order_id,
    SUM(r.quantity_returned * oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur) AS ret_rev,
    SUM(r.quantity_returned * oi.unit_cost * o.fx_rate_to_eur) AS ret_cost
  FROM returns r
  JOIN order_items oi ON oi.order_item_id = r.order_item_id
  JOIN orders o ON o.order_id = oi.order_id
  GROUP BY 1
),
ship_counts AS (SELECT order_id, COUNT(*) AS n_ships FROM shipments GROUP BY 1),
combined AS (
  SELECT f.order_id, s.n_ships,
    f.gross_rev - COALESCE(rt.ret_rev, 0) AS net_rev,
    f.gross_cost - COALESCE(rt.ret_cost, 0) AS net_cost
  FROM order_fin f
  JOIN ship_counts s ON s.order_id = f.order_id
  LEFT JOIN ret_by_order rt ON rt.order_id = f.order_id
)
SELECT CASE WHEN n_ships > 1 THEN 'split (2+ shipments)' ELSE 'single shipment' END AS fulfillment_type,
  COUNT(*) AS n_orders,
  ROUND(AVG(net_rev), 2) AS avg_net_revenue,
  ROUND(100.0 * SUM(net_rev - net_cost) / SUM(net_rev), 2) AS margin_pct,
  ROUND(AVG(net_rev - net_cost), 2) AS avg_profit_per_order
FROM combined
GROUP BY 1;
```

**Answer:** Split-fulfillment orders are slightly *more* profitable on average, not less. Split orders (404 of them) average €480.24 net revenue and €253.09 profit per order at a 52.70% margin, vs. single-shipment orders (1,527 of them) averaging €445.16 net revenue and €233.45 profit per order at a 52.44% margin. The difference is modest but consistently favors split orders — likely because larger/more complex orders (which need multiple shipments) simply carry more revenue, with margin essentially unchanged.

---

## Q14: Based on revenue and margin trends, does it look worthwhile for Sahara Retail to expand its Swiss operations relative to the Eurozone markets?

```sql
WITH line AS (
  SELECT CASE WHEN o.country = 'Switzerland' THEN 'Switzerland' ELSE 'Eurozone (FR/DE/BE)' END AS grp,
    date_trunc('quarter', o.order_date) AS q, oi.order_item_id,
    oi.unit_price * oi.quantity * (1 - oi.line_discount_pct) * o.fx_rate_to_eur AS net_rev,
    oi.unit_cost * oi.quantity * o.fx_rate_to_eur AS net_cost,
    oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur AS unit_net_price,
    oi.unit_cost * o.fx_rate_to_eur AS unit_net_cost
  FROM orders o
  JOIN order_items oi ON oi.order_id = o.order_id
  WHERE o.status = 'completed'
),
ret AS (SELECT order_item_id, SUM(quantity_returned) AS qty_ret FROM returns GROUP BY 1)
SELECT l.grp, l.q,
  ROUND(SUM(l.net_rev) - SUM(COALESCE(r.qty_ret, 0) * l.unit_net_price), 2) AS net_revenue,
  ROUND(100.0 * ((SUM(l.net_rev) - SUM(COALESCE(r.qty_ret, 0) * l.unit_net_price)) - (SUM(l.net_cost) - SUM(COALESCE(r.qty_ret, 0) * l.unit_net_cost))) / (SUM(l.net_rev) - SUM(COALESCE(r.qty_ret, 0) * l.unit_net_price)), 2) AS margin_pct
FROM line l
LEFT JOIN ret r ON r.order_item_id = l.order_item_id
GROUP BY 1, 2
ORDER BY 1, 2;
```

**Answer:** Not obviously — the case for expansion is weak. Margins are essentially identical between Switzerland (~50–53%) and the Eurozone markets (~52.5–52.8%), so there's no profitability edge in Switzerland. On revenue, Switzerland (converted to EUR) has trended flat-to-down over the six quarters (€30,539 → €27,560 → €27,203 → €22,850 → €23,524 → €27,105, i.e. below its 2024-Q3 starting point), while the combined Eurozone markets are roughly 4–5x larger and, aside from the France return anomaly in Q3 2025, ended the period at their highest quarterly revenue (€137,766 in Q4 2025). With similar margins but no revenue growth and much smaller scale, Switzerland does not look like the priority for expansion relative to the larger, more resilient Eurozone markets.

---

## Q15: Would the elevated return activity in France in Q3 2025 be visible if we only looked at cancelled orders?

```sql
SELECT date_trunc('quarter', order_date) AS q, COUNT(*) AS n_cancelled
FROM orders
WHERE country = 'France' AND status = 'cancelled'
GROUP BY 1
ORDER BY 1;

-- returns tied specifically to France's cancelled orders, by order quarter
SELECT date_trunc('quarter', o.order_date) AS q, COUNT(*) AS n_returns, SUM(r.quantity_returned) AS qty
FROM returns r
JOIN order_items oi ON oi.order_item_id = r.order_item_id
JOIN orders o ON o.order_id = oi.order_id
WHERE o.country = 'France' AND o.status = 'cancelled'
GROUP BY 1
ORDER BY 1;
```

**Answer:** No. Cancelled French orders in Q3 2025 numbered only 2 — actually the lowest of any quarter in the dataset (other quarters had 3–6) — and only 6 returns (10 units) are tied to France's cancelled orders across the entire dataset, concentrated in Q3–Q4 2025. The real spike (159 return events / 278 units returned in Q3 2025, ~€26,533) sits almost entirely on *completed* orders. Looking only at cancelled orders would completely miss the elevated return activity — it would even look like cancellations were unusually low that quarter.

---

## Q16: Identify the top 10 customers by net revenue across all four markets in 2025.

```sql
WITH line AS (
  SELECT o.customer_id, oi.order_item_id,
    oi.unit_price * oi.quantity * (1 - oi.line_discount_pct) * o.fx_rate_to_eur AS net_rev,
    oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur AS unit_net_price
  FROM orders o
  JOIN order_items oi ON oi.order_id = o.order_id
  WHERE o.status = 'completed' AND o.order_date >= '2025-01-01' AND o.order_date <= '2025-12-31'
),
ret AS (SELECT order_item_id, SUM(quantity_returned) AS qty_ret FROM returns GROUP BY 1)
SELECT c.customer_id, c.name, c.country,
  ROUND(SUM(l.net_rev) - SUM(COALESCE(r.qty_ret, 0) * l.unit_net_price), 2) AS net_revenue_2025
FROM line l
LEFT JOIN ret r ON r.order_item_id = l.order_item_id
JOIN customers c ON c.customer_id = l.customer_id
GROUP BY 1, 2, 3
ORDER BY 4 DESC
LIMIT 10;
```

**Answer:**
1. Richard Lawson (Switzerland) — €7,673.85
2. Lawrence Perry (Germany) — €6,089.11
3. Heidi Owen (Germany) — €5,674.09
4. Jordan Bullock (France) — €5,089.79
5. Thomas Romero (France) — €5,034.23
6. Travis Wise (Germany) — €4,792.96
7. Tanya Rogers (Germany) — €4,755.30
8. Doris Hall (France) — €4,706.75
9. Stephanie Gilbert (Germany) — €4,621.37
10. John Boone (France) — €4,508.47

(All figures are net of returns and converted to EUR at each order's fx rate.)

---

## Q17: Identify which customers could be offered a 10% discount while keeping margin above 20%, across all markets.

```sql
WITH line AS (
  SELECT o.customer_id, oi.order_item_id,
    oi.unit_price * oi.quantity * o.fx_rate_to_eur AS list_rev,
    oi.unit_cost * oi.quantity * o.fx_rate_to_eur AS cost,
    oi.unit_cost * o.fx_rate_to_eur AS unit_net_cost
  FROM orders o
  JOIN order_items oi ON oi.order_id = o.order_id
  WHERE o.status = 'completed'
),
ret AS (SELECT order_item_id, SUM(quantity_returned) AS qty_ret FROM returns GROUP BY 1),
cust_agg AS (
  SELECT l.customer_id,
    SUM(l.list_rev) * 0.9 AS net_rev_at_10pct_disc,
    SUM(l.list_rev) * 0.9 - (SUM(l.cost) - SUM(COALESCE(r.qty_ret, 0) * l.unit_net_cost)) AS profit_at_10pct_disc
  FROM line l
  LEFT JOIN ret r ON r.order_item_id = l.order_item_id
  GROUP BY 1
)
SELECT c.customer_id, c.name, c.country,
  ROUND(net_rev_at_10pct_disc, 2) AS proj_net_revenue_at_10pct_discount,
  ROUND(100.0 * profit_at_10pct_disc / net_rev_at_10pct_disc, 2) AS proj_margin_pct_at_10pct_discount
FROM cust_agg ca
JOIN customers c ON c.customer_id = ca.customer_id
WHERE net_rev_at_10pct_disc > 0
  AND 100.0 * profit_at_10pct_disc / net_rev_at_10pct_disc > 20
ORDER BY 5 DESC;
```

**Answer:** All 300 customers qualify. Applying a flat 10% discount to each customer's full purchase history (based on the actual list price and cost of the items they bought, net of returns) leaves a projected margin ranging from 42.5% (lowest customer) to 73.9% (highest), with an average of 52.7% — comfortably above the 20% floor for every single customer. This is because product cost consistently runs around 45% of list price across the catalog, and even a 10% discount only pushes margin down to roughly 1 − 0.45/0.9 ≈ 50% at the low end of typical cost ratios, far from the 20% threshold.

---

## Q18: Rank product categories by margin, using the prices customers actually paid rather than current catalog prices.

```sql
WITH line AS (
  SELECT p.category, oi.order_item_id,
    oi.unit_price * oi.quantity * (1 - oi.line_discount_pct) * o.fx_rate_to_eur AS net_rev,
    oi.unit_cost * oi.quantity * o.fx_rate_to_eur AS net_cost,
    oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur AS unit_net_price,
    oi.unit_cost * o.fx_rate_to_eur AS unit_net_cost
  FROM orders o
  JOIN order_items oi ON oi.order_id = o.order_id
  JOIN products p ON p.product_id = oi.product_id
  WHERE o.status = 'completed'
),
ret AS (SELECT order_item_id, SUM(quantity_returned) AS qty_ret FROM returns GROUP BY 1)
SELECT l.category,
  ROUND(SUM(l.net_rev) - SUM(COALESCE(r.qty_ret, 0) * l.unit_net_price), 2) AS net_revenue,
  ROUND(100.0 * ((SUM(l.net_rev) - SUM(COALESCE(r.qty_ret, 0) * l.unit_net_price)) - (SUM(l.net_cost) - SUM(COALESCE(r.qty_ret, 0) * l.unit_net_cost))) / (SUM(l.net_rev) - SUM(COALESCE(r.qty_ret, 0) * l.unit_net_price)), 2) AS margin_pct
FROM line l
LEFT JOIN ret r ON r.order_item_id = l.order_item_id
GROUP BY 1
ORDER BY 3 DESC;
```

**Answer:** Ranked by margin (net of returns, using each order line's actual transaction price and cost, not current catalog prices):
1. Kitchenware — 54.56%
2. Accessories — 53.10%
3. Outdoor — 52.44%
4. Home — 51.92%
5. Textiles — 51.72%
6. Lighting — 47.37%

---

## Q19: If VIP-segment customers are more profitable, which standard customers look most similar to VIP customers on their purchase history, and could be considered for promotion?

```sql
WITH cust_stats AS (
  SELECT o.customer_id,
    COUNT(DISTINCT o.order_id) AS n_orders,
    SUM(oi.unit_price * oi.quantity * (1 - oi.line_discount_pct) * o.fx_rate_to_eur) AS total_net_rev
  FROM orders o
  JOIN order_items oi ON oi.order_id = o.order_id
  WHERE o.status = 'completed'
  GROUP BY 1
),
current_seg AS (SELECT customer_id, segment FROM customer_segments WHERE valid_to IS NULL),
stats AS (
  SELECT s.customer_id, cs.segment, s.n_orders, s.total_net_rev, s.total_net_rev / s.n_orders AS aov
  FROM cust_stats s
  JOIN current_seg cs ON cs.customer_id = s.customer_id
),
agg_stats AS (
  SELECT AVG(n_orders) m_orders, STDDEV(n_orders) sd_orders,
         AVG(total_net_rev) m_rev, STDDEV(total_net_rev) sd_rev,
         AVG(aov) m_aov, STDDEV(aov) sd_aov
  FROM stats
),
vip_centroid AS (
  SELECT AVG((n_orders - m_orders) / sd_orders) c_orders,
         AVG((total_net_rev - m_rev) / sd_rev) c_rev,
         AVG((aov - m_aov) / sd_aov) c_aov
  FROM stats, agg_stats WHERE segment = 'VIP'
)
SELECT s.customer_id, c.name, c.country, s.n_orders,
  ROUND(s.total_net_rev, 2) AS total_net_rev, ROUND(s.aov, 2) AS aov,
  ROUND(SQRT(
    POWER((s.n_orders - a.m_orders) / a.sd_orders - v.c_orders, 2) +
    POWER((s.total_net_rev - a.m_rev) / a.sd_rev - v.c_rev, 2) +
    POWER((s.aov - a.m_aov) / a.sd_aov - v.c_aov, 2)
  ), 3) AS dist_to_vip_centroid
FROM stats s, agg_stats a, vip_centroid v
JOIN customers c ON c.customer_id = s.customer_id
WHERE s.segment = 'standard'
ORDER BY dist_to_vip_centroid ASC
LIMIT 15;
```

**Answer:** First, the premise doesn't really hold: as found in Q12, VIP customers are not meaningfully more profitable than standard customers (52.03% vs. 52.53% margin) — and on raw purchase totals, standard customers actually average slightly *more* full-period net revenue per customer (€3,146.89) than current VIP customers (€2,695.06), with similar order counts (6.50 vs. 5.94). So a margin-driven "promote to VIP" strategy has weak justification from this data.

That said, treating VIP customers' purchase-history profile (order count, total net revenue, average order value) as a target and finding standard customers closest to that profile (nearest-neighbor on standardized features) surfaces these candidates as most similar to the typical VIP customer:
1. Carmen Smith (Belgium) — 6 orders, €2,682.73 total, €447.12 AOV
2. Timothy Duncan (France) — 6 orders, €2,692.45 total, €448.74 AOV
3. Teresa Ramirez (France) — 6 orders, €2,699.51 total, €449.92 AOV
4. Erika Terry (Germany) — 6 orders, €2,648.11 total, €441.35 AOV
5. Andrew Stewart (France) — 6 orders, €2,808.05 total, €468.01 AOV
6. John Peterson (France) — 6 orders, €2,813.29 total, €468.88 AOV
7. Chad Baldwin (France) — 6 orders, €2,815.96 total, €469.33 AOV
8. Rebecca Ramsey (France) — 6 orders, €2,534.59 total, €422.43 AOV
9. Michael Santos (France) — 6 orders, €2,485.01 total, €414.17 AOV
10. Stephen Jones (Germany) — 6 orders, €2,901.62 total, €483.60 AOV

---

## Q20: Build a market-by-market summary of revenue, margin, and return rate for 2025 that a regional manager could use to decide which market to prioritize fixing first.

```sql
WITH line AS (
  SELECT o.country, oi.order_item_id, oi.quantity,
    oi.unit_price * oi.quantity * (1 - oi.line_discount_pct) * o.fx_rate_to_eur AS net_rev,
    oi.unit_cost * oi.quantity * o.fx_rate_to_eur AS net_cost,
    oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur AS unit_net_price,
    oi.unit_cost * o.fx_rate_to_eur AS unit_net_cost
  FROM orders o
  JOIN order_items oi ON oi.order_id = o.order_id
  WHERE o.status = 'completed' AND o.order_date >= '2025-01-01' AND o.order_date <= '2025-12-31'
),
ret AS (SELECT order_item_id, SUM(quantity_returned) AS qty_ret FROM returns GROUP BY 1)
SELECT l.country,
  ROUND(SUM(l.net_rev) - SUM(COALESCE(r.qty_ret, 0) * l.unit_net_price), 2) AS net_revenue_2025,
  ROUND(100.0 * ((SUM(l.net_rev) - SUM(COALESCE(r.qty_ret, 0) * l.unit_net_price)) - (SUM(l.net_cost) - SUM(COALESCE(r.qty_ret, 0) * l.unit_net_cost))) / (SUM(l.net_rev) - SUM(COALESCE(r.qty_ret, 0) * l.unit_net_price)), 2) AS margin_pct,
  ROUND(100.0 * SUM(COALESCE(r.qty_ret, 0)) / SUM(l.quantity), 2) AS return_rate_pct_by_qty
FROM line l
LEFT JOIN ret r ON r.order_item_id = l.order_item_id
GROUP BY 1
ORDER BY 2 DESC;
```

**Answer:**

| Market | Net Revenue 2025 (EUR) | Margin % | Return Rate % (by units) |
|---|---|---|---|
| France | 193,383.02 | 52.80% | 14.24% |
| Germany | 168,154.88 | 52.71% | 3.55% |
| Belgium | 101,911.36 | 52.15% | 3.53% |
| Switzerland | 100,682.29 | 52.52% | 3.35% |

All four markets run essentially the same margin (~52–53%), so margin is not a differentiator. France is by far the largest market by revenue but also has a return rate roughly 4x every other market (14.24% vs. ~3.4–3.6%), almost entirely driven by the Q3 2025 return spike identified above (Q6/Q10/Q15). **France is the clear priority to fix first** — it is the biggest revenue base being eroded by an anomalous, concentrated return event, and resolving its root cause (rather than a chronic, market-wide issue) protects the single largest and otherwise healthy market.
