# Transcript: Sahara Retail Eval Questions

All queries run against `data/retail.duckdb` using DuckDB via Python. All monetary
figures are converted to EUR using each order's `fx_rate_to_eur` (captured at order
time, since Switzerland trades in CHF and the rate moves over the period). All
revenue/cost figures use the actual price/cost recorded on each order line
(`order_items.unit_price` / `unit_cost`) rather than the current catalog price in
`product_price_history`, since prices changed over time and orders should reflect what
was actually charged at the time of purchase. "Net revenue" / "net margin" below means
after subtracting returned quantities (via the `returns` table); "gross revenue" means
before returns. Customer segment (VIP/standard) is resolved as-of the order date using
`customer_segment_history`, since segment membership changes over time (SCD).

A shared building block, `line_detail`, is used throughout:

```sql
WITH line_detail AS (
  SELECT
    oi.order_item_id, oi.order_id, o.customer_id, o.order_date, o.country, o.currency,
    o.fx_rate_to_eur, o.status,
    oi.product_id, p.category, p.subcategory,
    oi.quantity, oi.unit_price, oi.unit_cost, oi.line_discount_pct,
    COALESCE(r.quantity_returned,0) AS quantity_returned,
    (oi.quantity * oi.unit_price * (1-oi.line_discount_pct)) * o.fx_rate_to_eur AS gross_revenue_eur,
    (oi.quantity * oi.unit_cost) * o.fx_rate_to_eur AS gross_cost_eur,
    (COALESCE(r.quantity_returned,0) * oi.unit_price * (1-oi.line_discount_pct)) * o.fx_rate_to_eur AS returned_revenue_eur,
    (COALESCE(r.quantity_returned,0) * oi.unit_cost) * o.fx_rate_to_eur AS returned_cost_eur
  FROM order_items oi
  JOIN orders o ON oi.order_id = o.order_id
  JOIN products p ON oi.product_id = p.product_id
  LEFT JOIN returns r ON oi.order_item_id = r.order_item_id
)
```

---

## Q1: What was total revenue (in EUR) for each of the four markets (France, Germany, Belgium, Switzerland) over the full data period?

```sql
WITH line_detail AS ( ... see shared block above ... )
SELECT country, ROUND(SUM(gross_revenue_eur),2) AS revenue_eur
FROM line_detail
WHERE status='completed'
GROUP BY country ORDER BY country
```

**Answer:** Over the full data period (2024-07-01 to 2025-12-31), total revenue from completed orders, converted to EUR, was: France €325,547.80, Germany €267,834.12, Belgium €170,895.14, and Switzerland €165,332.25 (Switzerland's CHF-denominated orders were converted to EUR using each order's FX rate).

---

## Q2: What was the average order value in Q1 2025, and how does it compare to the average order value in Q4 2024?

```sql
WITH line_detail AS ( ... )
SELECT
  CASE WHEN order_date BETWEEN '2025-01-01' AND '2025-03-31' THEN 'Q1_2025'
       WHEN order_date BETWEEN '2024-10-01' AND '2024-12-31' THEN 'Q4_2024' END AS period,
  ROUND(SUM(gross_revenue_eur) / COUNT(DISTINCT order_id), 2) AS avg_order_value_eur,
  COUNT(DISTINCT order_id) AS n_orders
FROM line_detail
WHERE status='completed'
  AND ((order_date BETWEEN '2025-01-01' AND '2025-03-31') OR (order_date BETWEEN '2024-10-01' AND '2024-12-31'))
GROUP BY period
```

**Answer:** Average order value (completed orders, EUR, using the price actually paid at the time — not current catalog prices) was €490.88 in Q1 2025 (290 orders) versus €474.87 in Q4 2024 (340 orders). Q1 2025's average order value was about €16 (3.4%) higher than Q4 2024, even though order count was lower.

---

## Q3: How many completed orders were placed in each quarter of 2025?

```sql
SELECT date_trunc('quarter', order_date) AS quarter, COUNT(*) AS n_orders
FROM orders
WHERE status='completed' AND order_date BETWEEN '2025-01-01' AND '2025-12-31'
GROUP BY quarter ORDER BY quarter
```

**Answer:** Completed orders by quarter in 2025: Q1 = 290, Q2 = 308, Q3 = 315, Q4 = 362. Order volume grew steadily through the year.

---

## Q4: How many shipments were sent to Belgium in total?

```sql
SELECT COUNT(*)
FROM shipments s JOIN orders o ON s.order_id = o.order_id
WHERE o.country='Belgium'
```

**Answer:** 464 shipments were sent to Belgium in total over the data period.

---

## Q5: What is the total quantity of items ordered, broken down by product category?

```sql
WITH line_detail AS ( ... )
SELECT category, SUM(quantity) AS total_qty
FROM line_detail
WHERE status='completed'
GROUP BY category ORDER BY total_qty DESC
```

**Answer:** Total units ordered (completed orders) by category: Outdoor 2,886, Accessories 2,188, Home 1,794, Textiles 1,293, Kitchenware 940, Lighting 550.

---

## Q6: Why did net revenue in France decline in Q3 2025 compared to Q2 2025?

```sql
WITH line_detail AS ( ... )
SELECT
  CASE WHEN order_date BETWEEN '2025-04-01' AND '2025-06-30' THEN 'Q2_2025'
       WHEN order_date BETWEEN '2025-07-01' AND '2025-09-30' THEN 'Q3_2025' END AS period,
  ROUND(SUM(gross_revenue_eur),2) AS gross_revenue_eur,
  ROUND(SUM(returned_revenue_eur),2) AS returned_revenue_eur,
  ROUND(SUM(gross_revenue_eur - returned_revenue_eur),2) AS net_revenue_eur,
  COUNT(DISTINCT order_id) AS n_orders,
  SUM(quantity) AS gross_qty,
  SUM(quantity_returned) AS returned_qty
FROM line_detail
WHERE status='completed' AND country='France'
  AND ((order_date BETWEEN '2025-04-01' AND '2025-06-30') OR (order_date BETWEEN '2025-07-01' AND '2025-09-30'))
GROUP BY period;

-- return reasons breakdown
SELECT r.reason, COUNT(*) n, SUM(r.quantity_returned) qty, ROUND(SUM(ld.returned_revenue_eur),2) eur
FROM line_detail ld
JOIN returns r ON ld.order_item_id = r.order_item_id
WHERE ld.country='France' AND ld.order_date BETWEEN '2025-07-01' AND '2025-09-30'
GROUP BY r.reason ORDER BY eur DESC
```

**Answer:** It was not driven by weaker sales — gross revenue was actually flat-to-up (€55,482 in Q2 2025 vs €56,531 in Q3 2025, on more orders: 107 vs 117). The decline in *net* revenue (€54,907 → €29,998, a ~45% drop) was caused almost entirely by a spike in returns: only 7 units were returned in Q2 2025 versus 278 units in Q3 2025 (return rate jumped from ~1.3% to ~46% of units sold). The Q3 returns were spread fairly evenly across four reasons — damaged_in_transit (70 units, €7,382), changed_mind (73 units, €7,233), fulfillment_delay (79 units, €6,969), and wrong_item (66 units, €6,091) — suggesting a broad operational/fulfillment issue in that quarter rather than a demand problem.

---

## Q7: What share of France's revenue in Q3 2025 came from customers who were VIP segment at the time of purchase?

```sql
WITH line_detail AS ( ... )
SELECT h.segment, ROUND(SUM(ld.gross_revenue_eur),2) AS revenue_eur
FROM line_detail ld
JOIN customer_segment_history h ON ld.customer_id = h.customer_id
  AND ld.order_date >= h.valid_from AND (h.valid_to IS NULL OR ld.order_date < h.valid_to)
WHERE ld.status='completed' AND ld.country='France'
  AND ld.order_date BETWEEN '2025-07-01' AND '2025-09-30'
GROUP BY h.segment
```

**Answer:** Of France's €56,530.76 gross revenue in Q3 2025, €4,112.16 (about 7.3%) came from customers who were VIP-segment *at the time of purchase* (using each customer's segment history, not their current segment). The remaining ~92.7% came from customers who were standard segment when they ordered.

---

## Q8: Has average revenue per unit sold in the "Kitchenware" category changed over the data period, and why?

```sql
WITH line_detail AS ( ... )
SELECT date_trunc('quarter', order_date) AS quarter,
  ROUND(SUM(gross_revenue_eur) / SUM(quantity), 2) AS avg_rev_per_unit_eur,
  SUM(quantity) AS qty
FROM line_detail
WHERE status='completed' AND category='Kitchenware'
GROUP BY quarter ORDER BY quarter;

-- underlying price/discount trend (actual transacted prices, not catalog)
SELECT date_trunc('quarter', order_date) AS quarter,
  ROUND(AVG(unit_price),2) AS avg_list_unit_price,
  ROUND(AVG(line_discount_pct),4) AS avg_discount
FROM line_detail
WHERE status='completed' AND category='Kitchenware'
GROUP BY quarter ORDER BY quarter
```

**Answer:** Average revenue per unit sold in Kitchenware has stayed fairly stable, in the €113–€127 range per quarter (2024 Q3: €114.13, Q4: €114.07; 2025 Q1: €127.00, Q2: €121.22, Q3: €122.84, Q4: €113.03) — no strong upward or downward trend, just quarter-to-quarter noise. This tracks the underlying transacted unit price (from `order_items`, not the current catalog price), which similarly bounced between about €119 and €134 with average discounts staying in a narrow 4.2%–5.3% band. So there's been mild fluctuation but no sustained change in per-unit revenue for Kitchenware over the period.

---

## Q9: Is average revenue per shipment declining for orders that required split fulfillment (more than one shipment)?

```sql
WITH line_detail AS ( ... ),
order_rev AS (
  SELECT order_id, order_date, SUM(gross_revenue_eur) AS order_revenue_eur
  FROM line_detail WHERE status='completed' GROUP BY order_id, order_date
),
order_ship AS (
  SELECT order_id, COUNT(*) AS n_shipments FROM shipments GROUP BY order_id
)
SELECT date_trunc('quarter', orv.order_date) AS quarter,
  ROUND(SUM(orv.order_revenue_eur) / SUM(os.n_shipments), 2) AS avg_revenue_per_shipment_eur,
  COUNT(*) AS n_split_orders
FROM order_rev orv
JOIN order_ship os ON orv.order_id = os.order_id
WHERE os.n_shipments >= 2
GROUP BY quarter ORDER BY quarter
```

Note: revenue is divided by the number of shipments *for the order*, so a single order's revenue isn't double-counted across its multiple shipment rows.

**Answer:** There was a decline through most of the period — average revenue per shipment for split-fulfillment orders fell from €225.76 (2024 Q3) to a low of €187.62 (2025 Q3) — but it recovered to €222.96 in 2025 Q4, back near the starting level. So the metric declined for roughly a year (mid-2024 through mid/late-2025) but is not declining overall by the end of the data period; the most recent quarter reversed the trend.

---

## Q10: Which market has the highest return rate, and in which quarter does it peak?

```sql
WITH line_detail AS ( ... )
SELECT country,
  ROUND(SUM(quantity_returned)::DOUBLE / SUM(quantity), 4) AS overall_return_rate
FROM line_detail
WHERE status='completed'
GROUP BY country ORDER BY overall_return_rate DESC;

-- by quarter to find the peak
SELECT country, date_trunc('quarter', order_date) AS quarter,
  SUM(quantity_returned) AS returned_qty, SUM(quantity) AS ordered_qty,
  ROUND(SUM(quantity_returned)::DOUBLE / SUM(quantity), 4) AS return_rate
FROM line_detail
WHERE status='completed'
GROUP BY country, quarter ORDER BY country, quarter
```

**Answer:** France has by far the highest return rate overall (10.9% of units returned, vs 3.8% for Switzerland, 3.5% for Germany, and 2.9% for Belgium). Its return rate peaks sharply in Q3 2025, at 45.9% of units ordered — an extreme outlier compared to every other market/quarter in the dataset (all others are in the 1–6% range), driven by the returns spike described in Q6.

---

## Q11: Could Sahara Retail increase discounts for French customers without dropping overall margin below 20%?

```sql
WITH line_detail AS ( ... )
SELECT
  ROUND(SUM(gross_revenue_eur - returned_revenue_eur),2) AS net_revenue_eur,
  ROUND(SUM(gross_cost_eur - returned_cost_eur),2) AS net_cost_eur,
  ROUND( (SUM(gross_revenue_eur-returned_revenue_eur) - SUM(gross_cost_eur-returned_cost_eur))
       / SUM(gross_revenue_eur-returned_revenue_eur), 4) AS current_margin
FROM line_detail
WHERE status='completed' AND country='France';

-- simulate an additional across-the-board discount on top of current pricing (cost unchanged)
SELECT extra_disc,
  ROUND(SUM(new_net_rev),2) AS new_net_revenue_eur,
  ROUND(SUM(new_net_rev - new_net_cost) / SUM(new_net_rev), 4) AS new_margin
FROM (
  SELECT *,
    (gross_revenue_eur - returned_revenue_eur) * (1-extra_disc) AS new_net_rev,
    (gross_cost_eur - returned_cost_eur) AS new_net_cost
  FROM line_detail, (SELECT unnest([0.0,0.02,0.05,0.08,0.10,0.15]) AS extra_disc) x
  WHERE status='completed' AND country='France'
) t
GROUP BY extra_disc ORDER BY extra_disc
```

**Answer:** Yes, there is substantial room. France's current net margin is about 52.7%. Simulating an additional across-the-board discount on top of current pricing (holding cost per unit fixed), margin only falls to about 47.5% at a 10-point extra discount and about 44.4% at a 15-point extra discount — both far above the 20% floor. France could increase discounts well beyond what's being modeled here (in the ballpark of 30+ extra points) before margin would approach 20%, so a modest discount increase (e.g., 5-10 points) is very safe from a margin standpoint.

---

## Q12: Is the VIP customer segment actually more profitable (higher margin) than standard customers?

```sql
WITH line_detail AS ( ... )
SELECT h.segment,
  ROUND(SUM(ld.gross_revenue_eur - ld.returned_revenue_eur),2) AS net_revenue_eur,
  ROUND( (SUM(ld.gross_revenue_eur-ld.returned_revenue_eur) - SUM(ld.gross_cost_eur-ld.returned_cost_eur))
       / SUM(ld.gross_revenue_eur-ld.returned_revenue_eur), 4) AS margin
FROM line_detail ld
JOIN customer_segment_history h ON ld.customer_id = h.customer_id
  AND ld.order_date >= h.valid_from AND (h.valid_to IS NULL OR ld.order_date < h.valid_to)
WHERE ld.status='completed'
GROUP BY h.segment
```

**Answer:** No — margin is essentially the same, and standard customers are actually marginally higher: 52.53% for standard-segment purchases vs 52.03% for VIP-segment purchases (segment measured as-of each order date). VIP status does not translate into a materially higher margin in this data.

---

## Q13: Are orders that required split fulfillment (2+ shipments) more or less profitable on average than single-shipment orders?

```sql
WITH line_detail AS ( ... ),
order_agg AS (
  SELECT order_id, SUM(gross_revenue_eur-returned_revenue_eur) AS net_rev, SUM(gross_cost_eur-returned_cost_eur) AS net_cost
  FROM line_detail WHERE status='completed' GROUP BY order_id
),
order_ship AS (
  SELECT order_id, COUNT(*) AS n_shipments FROM shipments GROUP BY order_id
)
SELECT CASE WHEN os.n_shipments >= 2 THEN 'split (2+)' ELSE 'single' END AS fulfillment_type,
  COUNT(*) AS n_orders,
  ROUND(AVG(oa.net_rev),2) AS avg_net_revenue_per_order,
  ROUND(AVG(oa.net_rev - oa.net_cost),2) AS avg_profit_per_order,
  ROUND(SUM(oa.net_rev-oa.net_cost)/SUM(oa.net_rev),4) AS margin
FROM order_agg oa JOIN order_ship os ON oa.order_id=os.order_id
GROUP BY fulfillment_type
```

**Answer:** Split-fulfillment orders (2+ shipments) are slightly more profitable, not less: average net revenue per order is €482.31 (vs €447.29 for single-shipment orders), average profit per order is €253.74 (vs €234.73), and margin is marginally higher (52.6% vs 52.5%). The difference is small, but split-fulfillment orders — which tend to be larger, multi-item orders — are at least as, if not slightly more, profitable per order.

---

## Q14: Based on revenue and margin trends, does it look worthwhile for Sahara Retail to expand its Swiss operations relative to the Eurozone markets?

```sql
WITH line_detail AS ( ... )
SELECT CASE WHEN country='Switzerland' THEN 'Switzerland' ELSE 'Eurozone' END AS market_group,
  date_trunc('quarter', order_date) AS quarter,
  ROUND(SUM(gross_revenue_eur - returned_revenue_eur),2) AS net_revenue_eur,
  ROUND( (SUM(gross_revenue_eur-returned_revenue_eur)-SUM(gross_cost_eur-returned_cost_eur))
       / SUM(gross_revenue_eur-returned_revenue_eur), 4) AS margin
FROM line_detail
WHERE status='completed'
GROUP BY market_group, quarter ORDER BY market_group, quarter
```

**Answer:** Not obviously — margin is comparable between the two groups (both hover around 51-53% every quarter, with no consistent gap), so there's no profitability advantage to expanding in Switzerland specifically. On revenue, Switzerland (all figures converted to EUR at the order-date FX rate) shows no growth trend: quarterly net revenue moved from €30,539 → €27,560 → €27,203 → €22,850 → €23,524 → €27,105 across the six quarters — flat to slightly down, not growing. The combined Eurozone markets (France, Germany, Belgium) are 4-5x larger in revenue and also fairly flat/quarter-noisy rather than clearly trending up. Given Switzerland shows no revenue growth momentum and no margin edge over the Eurozone markets, the trend data doesn't build a strong case for prioritizing Swiss expansion — the Eurozone markets remain both larger and at least as profitable.

---

## Q15: Would the elevated return activity in France in Q3 2025 be visible if we only looked at cancelled orders?

```sql
SELECT country, date_trunc('quarter', order_date) AS quarter, status, COUNT(*) n
FROM orders WHERE country='France' AND order_date BETWEEN '2025-01-01' AND '2025-12-31'
GROUP BY country, quarter, status ORDER BY quarter, status
```

**Answer:** No. Cancelled order counts for France in 2025 stayed flat and low all year (3, 3, 2, and 3 cancelled orders in Q1–Q4 respectively) — there is no spike in Q3 2025 in the cancellation data at all. The elevated return activity (278 units returned, a 46% return rate) is a completely separate phenomenon from order cancellations: it happens on *completed* orders, item-by-item, after delivery. Looking only at cancelled-order counts would completely miss this issue — you'd need to look at the `returns` table specifically to see it.

---

## Q16: Identify the top 10 customers by net revenue across all four markets in 2025.

```sql
WITH line_detail AS ( ... )
SELECT ld.customer_id, c.name, c.country,
  ROUND(SUM(ld.gross_revenue_eur - ld.returned_revenue_eur),2) AS net_revenue_eur
FROM line_detail ld
JOIN customers c ON ld.customer_id = c.customer_id
WHERE ld.status='completed' AND ld.order_date BETWEEN '2025-01-01' AND '2025-12-31'
GROUP BY ld.customer_id, c.name, c.country
ORDER BY net_revenue_eur DESC
LIMIT 10
```

**Answer:** The top 10 customers by 2025 net revenue (EUR) were:
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

---

## Q17: Identify which customers could be offered a 10% discount while keeping margin above 20%, across all markets.

```sql
WITH line_detail AS ( ... )
SELECT ld.customer_id,
  (SUM(ld.gross_revenue_eur-ld.returned_revenue_eur)*0.9 - SUM(ld.gross_cost_eur-ld.returned_cost_eur))
    / (SUM(ld.gross_revenue_eur-ld.returned_revenue_eur)*0.9) AS margin_after_10pct_discount
FROM line_detail ld
WHERE ld.status='completed'
GROUP BY ld.customer_id
HAVING SUM(ld.gross_revenue_eur-ld.returned_revenue_eur) > 0
   AND (SUM(ld.gross_revenue_eur-ld.returned_revenue_eur)*0.9 - SUM(ld.gross_cost_eur-ld.returned_cost_eur))
        / (SUM(ld.gross_revenue_eur-ld.returned_revenue_eur)*0.9) > 0.20
```

**Answer:** All 300 customers qualify — applying an additional 10% discount to each customer's full purchase history (with cost held fixed) still leaves every single customer's margin above 20% (the lowest resulting margin across all customers was about 35.7%, for the customer with the thinnest existing margin). Individual margins-after-discount range roughly from 35.7% up to about 52.9%, so a 10% discount could safely be offered company-wide without any customer's margin dropping below the 20% floor.

---

## Q18: Rank product categories by margin, using the prices customers actually paid rather than current catalog prices.

```sql
WITH line_detail AS ( ... )
SELECT category,
  ROUND(SUM(gross_revenue_eur - returned_revenue_eur),2) AS net_revenue_eur,
  ROUND(SUM(gross_cost_eur - returned_cost_eur),2) AS net_cost_eur,
  ROUND( (SUM(gross_revenue_eur-returned_revenue_eur) - SUM(gross_cost_eur-returned_cost_eur))
       / SUM(gross_revenue_eur-returned_revenue_eur), 4) AS margin
FROM line_detail
WHERE status='completed'
GROUP BY category ORDER BY margin DESC
```

(`line_detail` uses `order_items.unit_price`/`unit_cost` — the price and cost actually recorded on the transaction — rather than `product_price_history`, which reflects current/point-in-time catalog pricing and would not capture what was actually paid at order time.)

**Answer:** Ranked by margin (highest to lowest), using actual transacted prices: 1) Kitchenware — 54.6%, 2) Accessories — 53.1%, 3) Outdoor — 52.4%, 4) Home — 51.9%, 5) Textiles — 51.7%, 6) Lighting — 47.4%. Lighting is notably the lowest-margin category; Kitchenware is the highest.

---

## Q19: If VIP-segment customers are more profitable, which standard customers look most similar to VIP customers on their purchase history, and could be considered for promotion?

```sql
WITH line_detail AS ( ... ),
cust_orders AS (
  SELECT ld.customer_id, ld.order_id, SUM(ld.gross_revenue_eur - ld.returned_revenue_eur) AS order_net_rev,
    SUM(ld.gross_cost_eur - ld.returned_cost_eur) AS order_net_cost
  FROM line_detail ld WHERE ld.status='completed'
  GROUP BY ld.customer_id, ld.order_id
),
cust_profile AS (
  SELECT customer_id, COUNT(*) AS n_orders, ROUND(AVG(order_net_rev),2) AS avg_order_value,
    ROUND(SUM(order_net_rev - order_net_cost)/SUM(order_net_rev),4) AS margin,
    ROUND(SUM(order_net_rev),2) AS total_net_rev
  FROM cust_orders GROUP BY customer_id
),
cust_current_segment AS (
  SELECT customer_id, segment FROM customer_segment_history WHERE valid_to IS NULL
)
-- VIP vs standard centroid comparison
SELECT s.segment, COUNT(*) n_customers, ROUND(AVG(p.avg_order_value),2) avg_aov,
  ROUND(AVG(p.n_orders),2) avg_orders, ROUND(AVG(p.margin),4) avg_margin
FROM cust_profile p JOIN cust_current_segment s ON p.customer_id = s.customer_id
GROUP BY s.segment;

-- standard customers whose order count and AOV match/exceed the VIP profile
SELECT p.customer_id, c.name, c.country, p.n_orders, p.avg_order_value, p.margin, p.total_net_rev
FROM cust_profile p
JOIN cust_current_segment s ON p.customer_id = s.customer_id
JOIN customers c ON p.customer_id = c.customer_id
WHERE s.segment='standard' AND p.n_orders >= 6 AND p.avg_order_value >= 500
ORDER BY p.avg_order_value DESC, p.n_orders DESC
LIMIT 15
```

**Answer:** First, the premise doesn't hold in this data: VIP customers are not more profitable than standard customers on average (VIP average order value €426.58, margin 51.9%, vs standard average order value €456.72, margin 52.4% — standard is actually marginally ahead on both). So there isn't a profitability gap to promote standard customers "up" to. That said, if the business still wants to identify standard customers who purchase like VIPs (i.e., frequent, high-value buyers, since VIP status is presumably driven by purchase history/value per the glossary), the standard customers with the highest order frequency and order value — and thus the strongest promotion candidates by that behavioral definition — include David Medina (France, 7 orders, €754.87 AOV), Justin Riley (Switzerland, 6 orders, €754.35 AOV), Marc Lynch (Germany, 7 orders, €709.90 AOV), Denise Weber (Switzerland, 10 orders, €703.77 AOV), and Richard Lawson (Switzerland, 15 orders, €651.38 AOV, €9,770.76 total net revenue — the single highest-spending customer in the dataset and still classified standard).

---

## Q20: Build a market-by-market summary of revenue, margin, and return rate for 2025 that a regional manager could use to decide which market to prioritize fixing first.

```sql
WITH line_detail AS ( ... )
SELECT country,
  ROUND(SUM(gross_revenue_eur - returned_revenue_eur),2) AS net_revenue_eur,
  ROUND( (SUM(gross_revenue_eur-returned_revenue_eur) - SUM(gross_cost_eur-returned_cost_eur))
       / SUM(gross_revenue_eur-returned_revenue_eur), 4) AS margin,
  ROUND(SUM(quantity_returned)::DOUBLE / SUM(quantity), 4) AS return_rate,
  COUNT(DISTINCT order_id) AS n_orders
FROM line_detail
WHERE status='completed' AND order_date BETWEEN '2025-01-01' AND '2025-12-31'
GROUP BY country ORDER BY net_revenue_eur DESC
```

**Answer:** 2025 market summary (completed orders, EUR):

| Market | Net Revenue | Margin | Return Rate | Orders |
|---|---|---|---|---|
| France | €193,383.02 | 52.8% | 14.2% | 464 |
| Germany | €168,154.88 | 52.7% | 3.6% | 359 |
| Belgium | €101,911.36 | 52.2% | 3.5% | 237 |
| Switzerland | €100,682.29 | 52.5% | 3.4% | 215 |

All four markets have essentially the same margin (~52-53%), so margin is not a differentiator here. France is the largest market by revenue and order count, but it also has by far the highest return rate (14.2% for the year, roughly 4x every other market), which is almost entirely attributable to the Q3 2025 returns anomaly discussed in Q6/Q10 (a 46% return rate that quarter alone). A regional manager should prioritize France first: it's the biggest market, so the returns issue has the largest absolute revenue impact, and the elevated return rate is a clear, fixable operational problem (fulfillment delays, damage in transit, wrong items) rather than a demand or pricing issue.

