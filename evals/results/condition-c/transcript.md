## Q1: What was total revenue (in EUR) for each of the four markets (France, Germany, Belgium, Switzerland) over the full data period?

```sql
WITH li AS (
  SELECT
    oi.order_item_id, oi.order_id,
    (oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_price * (1 - oi.line_discount_pct) AS net_rev_local
  FROM order_items oi
  LEFT JOIN returns r ON r.order_item_id = oi.order_item_id
)
SELECT o.country,
  ROUND(SUM(li.net_rev_local * o.fx_rate_to_eur), 2) AS revenue_eur
FROM li
JOIN orders o ON o.order_id = li.order_id
WHERE o.status = 'completed'
GROUP BY o.country
ORDER BY o.country;
```

**Answer:** Total net revenue (completed orders, returns netted, converted to EUR) over 2024-07-01 to 2025-12-31: France €290,224.44, Germany €258,889.36, Belgium €165,879.78, Switzerland €158,781.01.

## Q2: What was the average order value in Q1 2025, and how does it compare to the average order value in Q4 2024?

```sql
WITH li AS (
  SELECT
    oi.order_item_id, oi.order_id,
    (oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_price * (1 - oi.line_discount_pct) AS net_rev_local
  FROM order_items oi
  LEFT JOIN returns r ON r.order_item_id = oi.order_item_id
)
SELECT
  CASE WHEN o.order_date BETWEEN '2025-01-01' AND '2025-03-31' THEN 'Q1 2025'
       WHEN o.order_date BETWEEN '2024-10-01' AND '2024-12-31' THEN 'Q4 2024' END AS period,
  ROUND(SUM(li.net_rev_local * o.fx_rate_to_eur) / COUNT(DISTINCT o.order_id), 2) AS aov_eur,
  COUNT(DISTINCT o.order_id) AS orders
FROM li
JOIN orders o ON o.order_id = li.order_id
WHERE o.status = 'completed'
  AND ((o.order_date BETWEEN '2025-01-01' AND '2025-03-31')
    OR (o.order_date BETWEEN '2024-10-01' AND '2024-12-31'))
GROUP BY 1
ORDER BY 1;
```

**Answer:** Average order value (net revenue / completed orders) was €472.35 in Q1 2025 (290 orders) versus €453.91 in Q4 2024 (340 orders) — Q1 2025 AOV was about 4.1% higher than Q4 2024, even though order volume was lower.

## Q3: How many completed orders were placed in each quarter of 2025?

```sql
SELECT date_trunc('quarter', order_date) AS quarter, COUNT(*) AS completed_orders
FROM orders
WHERE status = 'completed' AND order_date BETWEEN '2025-01-01' AND '2025-12-31'
GROUP BY 1
ORDER BY 1;
```

**Answer:** Q1 2025: 290 completed orders; Q2 2025: 308; Q3 2025: 315; Q4 2025: 362.

## Q4: How many shipments were sent to Belgium in total?

```sql
SELECT COUNT(*) AS shipments_to_belgium
FROM shipments s
JOIN orders o ON o.order_id = s.order_id
WHERE o.country = 'Belgium';
```

**Answer:** 484 shipments were sent to Belgium in total.

## Q5: What is the total quantity of items ordered, broken down by product category?

```sql
SELECT p.category, SUM(oi.quantity) AS total_qty
FROM order_items oi
JOIN products p ON p.product_id = oi.product_id
GROUP BY p.category
ORDER BY total_qty DESC;
```

**Answer:** Outdoor: 2,988 units; Accessories: 2,259; Home: 1,871; Textiles: 1,336; Kitchenware: 970; Lighting: 563 (gross ordered quantity, not netted for returns).

## Q6: Why did net revenue in France decline in Q3 2025 compared to Q2 2025?

```sql
-- Net revenue by quarter
WITH li AS (
  SELECT oi.order_item_id, oi.order_id,
    (oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_price * (1 - oi.line_discount_pct) AS net_rev_local
  FROM order_items oi
  LEFT JOIN returns r ON r.order_item_id = oi.order_item_id
)
SELECT
  CASE WHEN o.order_date BETWEEN '2025-07-01' AND '2025-09-30' THEN 'Q3 2025'
       WHEN o.order_date BETWEEN '2025-04-01' AND '2025-06-30' THEN 'Q2 2025' END AS period,
  ROUND(SUM(li.net_rev_local * o.fx_rate_to_eur), 2) AS revenue_eur,
  COUNT(DISTINCT o.order_id) AS orders
FROM li
JOIN orders o ON o.order_id = li.order_id
WHERE o.status = 'completed' AND o.country = 'France'
  AND ((o.order_date BETWEEN '2025-07-01' AND '2025-09-30')
    OR (o.order_date BETWEEN '2025-04-01' AND '2025-06-30'))
GROUP BY 1;

-- Diagnostic: gross revenue and return rate for the same two quarters
SELECT
  CASE WHEN o.order_date BETWEEN '2025-07-01' AND '2025-09-30' THEN 'Q3 2025'
       WHEN o.order_date BETWEEN '2025-04-01' AND '2025-06-30' THEN 'Q2 2025' END AS period,
  COUNT(DISTINCT o.order_id) AS completed_orders,
  SUM(oi.quantity) AS gross_qty,
  SUM(COALESCE(r.quantity_returned,0)) AS returned_qty,
  ROUND(SUM(COALESCE(r.quantity_returned,0)) * 1.0 / SUM(oi.quantity), 4) AS return_rate,
  ROUND(SUM(oi.quantity * oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur), 2) AS gross_rev_eur
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id
LEFT JOIN returns r ON r.order_item_id = oi.order_item_id
WHERE o.status = 'completed' AND o.country = 'France'
  AND ((o.order_date BETWEEN '2025-07-01' AND '2025-09-30')
    OR (o.order_date BETWEEN '2025-04-01' AND '2025-06-30'))
GROUP BY 1;
```

**Answer:** Net revenue in France fell from €54,907.00 in Q2 2025 (107 orders) to €29,997.81 in Q3 2025 (117 orders) — a ~45% decline. This was not a demand problem: gross (pre-return) revenue was essentially flat (€55,482 in Q2 vs €56,531 in Q3) and order count actually rose. The cause was a spike in partial returns: the return rate (quantity returned / quantity ordered) jumped from 1.26% in Q2 2025 to 45.87% in Q3 2025. Because these are partial, line-level returns that don't change `orders.status`, this drop is invisible unless returns are netted out explicitly at the line-item grain.

## Q7: What share of France's revenue in Q3 2025 came from customers who were VIP segment at the time of purchase?

```sql
WITH li AS (
  SELECT oi.order_item_id, oi.order_id, o.order_date, o.customer_id,
    (oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur AS net_rev_eur
  FROM order_items oi
  JOIN orders o ON o.order_id = oi.order_id
  LEFT JOIN returns r ON r.order_item_id = oi.order_item_id
  WHERE o.status = 'completed' AND o.country = 'France'
    AND o.order_date BETWEEN '2025-07-01' AND '2025-09-30'
),
seg AS (
  SELECT li.*, cs.segment
  FROM li
  LEFT JOIN customer_segments cs
    ON cs.customer_id = li.customer_id
    AND cs.valid_from <= li.order_date
    AND (cs.valid_to IS NULL OR li.order_date < cs.valid_to)
)
SELECT
  ROUND(SUM(CASE WHEN segment = 'VIP' THEN net_rev_eur ELSE 0 END), 2) AS vip_revenue,
  ROUND(SUM(net_rev_eur), 2) AS total_revenue,
  ROUND(SUM(CASE WHEN segment = 'VIP' THEN net_rev_eur ELSE 0 END) / SUM(net_rev_eur), 4) AS vip_share
FROM seg;
```

**Answer:** Customers who were VIP segment at the time of purchase contributed €2,941.76 of France's €29,997.81 net revenue in Q3 2025 — about 9.8% of the total.

## Q8: Has average revenue per unit sold in the "Kitchenware" category changed over the data period, and why?

```sql
SELECT date_trunc('quarter', o.order_date) AS quarter,
  ROUND(SUM((oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur)
        / NULLIF(SUM(oi.quantity - COALESCE(r.quantity_returned,0)), 0), 2) AS rev_per_unit_eur,
  SUM(oi.quantity - COALESCE(r.quantity_returned,0)) AS net_units
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id
JOIN products p ON p.product_id = oi.product_id
LEFT JOIN returns r ON r.order_item_id = oi.order_item_id
WHERE o.status = 'completed' AND p.category = 'Kitchenware'
GROUP BY 1
ORDER BY 1;

-- Discount trend, as a possible driver
SELECT date_trunc('quarter', o.order_date) AS quarter,
  ROUND(AVG(oi.line_discount_pct), 4) AS avg_discount_pct
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id
JOIN products p ON p.product_id = oi.product_id
WHERE o.status = 'completed' AND p.category = 'Kitchenware'
GROUP BY 1
ORDER BY 1;
```

**Answer:** Average revenue per unit sold (using the transaction-time price actually paid, not catalog price) in Kitchenware fluctuated in a narrow band across the data period: €115.08 (2024 Q3), €112.33 (2024 Q4), €126.03 (2025 Q1), €121.66 (2025 Q2), €123.89 (2025 Q3), €113.06 (2025 Q4). There is no sustained upward or downward trend — it moves up and back down within roughly €112–€126. Average line discount also stayed steady (4.2%–5.3% per quarter), so it isn't a discount-driven shift either. This looks like normal quarter-to-quarter mix variation rather than a structural change in what customers actually pay per unit, even though the underlying product catalog price for Kitchenware items did change over time (per `product_pricing`) — that catalog-price history is not the right source for this question, since `order_items` already stores the transaction-time price.

## Q9: Is average revenue per shipment declining for orders that required split fulfillment (more than one shipment)?

```sql
WITH order_rev AS (
  SELECT o.order_id, o.order_date, o.fx_rate_to_eur,
    SUM((oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_price * (1 - oi.line_discount_pct)) * o.fx_rate_to_eur AS net_rev_eur
  FROM orders o
  JOIN order_items oi ON oi.order_id = o.order_id
  LEFT JOIN returns r ON r.order_item_id = oi.order_item_id
  WHERE o.status = 'completed'
  GROUP BY o.order_id, o.order_date, o.fx_rate_to_eur
),
ship_counts AS (
  SELECT order_id, COUNT(*) AS n_shipments
  FROM shipments
  GROUP BY order_id
)
SELECT date_trunc('quarter', orr.order_date) AS quarter,
  ROUND(AVG(orr.net_rev_eur / sc.n_shipments), 2) AS avg_rev_per_shipment_eur,
  COUNT(*) AS n_split_orders
FROM order_rev orr
JOIN ship_counts sc ON sc.order_id = orr.order_id
WHERE sc.n_shipments >= 2
GROUP BY 1
ORDER BY 1;
```

**Answer:** No, there is no consistent decline. Average net revenue per shipment for split-fulfillment orders (2+ shipments) by quarter is: €230.27 (2024 Q3), €189.91 (2024 Q4), €179.17 (2025 Q1), €217.46 (2025 Q2), €196.44 (2025 Q3), €200.30 (2025 Q4). It dropped from the initial 2024 Q3 level and has since fluctuated in the €179–€217 range without a clear downward trajectory — the most recent quarter (€200.30) is similar to a year earlier (2024 Q4: €189.91), not lower. Note the metric is computed per order (order revenue split evenly across its shipment count), joining `orders` and `shipments` directly and never joining `shipments` to `order_items` (which would duplicate line items and inflate revenue).

## Q10: Which market has the highest return rate, and in which quarter does it peak?

```sql
SELECT o.country,
  ROUND(SUM(COALESCE(r.quantity_returned,0)) * 1.0 / SUM(oi.quantity), 4) AS return_rate
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id
LEFT JOIN returns r ON r.order_item_id = oi.order_item_id
WHERE o.status = 'completed'
GROUP BY 1
ORDER BY 2 DESC;

SELECT o.country, date_trunc('quarter', o.order_date) AS quarter,
  ROUND(SUM(COALESCE(r.quantity_returned,0)) * 1.0 / SUM(oi.quantity), 4) AS return_rate
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id
LEFT JOIN returns r ON r.order_item_id = oi.order_item_id
WHERE o.status = 'completed'
GROUP BY 1, 2
ORDER BY 1, 2;
```

**Answer:** France has the highest overall return rate at 10.86% (vs. Switzerland 3.76%, Germany 3.45%, Belgium 2.93%). France's return rate peaks sharply in Q3 2025 at 45.87%, far above its other quarters (which range roughly 1.3%–4.4%).

## Q11: Could Sahara Retail increase discounts for French customers without dropping overall margin below 20%?

```sql
WITH li AS (
  SELECT oi.order_id, o.fx_rate_to_eur,
    (oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur AS net_rev_eur,
    (oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_cost * (1 - oi.line_discount_pct) * o.fx_rate_to_eur AS net_cost_eur
  FROM order_items oi
  JOIN orders o ON o.order_id = oi.order_id
  LEFT JOIN returns r ON r.order_item_id = oi.order_item_id
  WHERE o.status = 'completed' AND o.country = 'France'
)
SELECT ROUND(SUM(net_rev_eur), 2) AS revenue, ROUND(SUM(net_cost_eur), 2) AS cost,
  ROUND((SUM(net_rev_eur) - SUM(net_cost_eur)) / SUM(net_rev_eur), 4) AS margin
FROM li;

-- Breakeven extra discount d solves: (revenue*(1-d) - cost) / (revenue*(1-d)) = 0.20
-- => d = 1 - cost / (0.8 * revenue)
```

**Answer:** Yes, there is substantial room. France's current margin is 54.98% (revenue €290,224.44, cost €130,665.71). Costs are unaffected by discounting, so margin declines as extra discount is applied to revenue while cost stays fixed. Solving for the breakeven point where margin hits exactly 20% gives an additional discount of about 43.7% on top of current pricing — far beyond any realistic discount increase. For example, even a substantial extra 15% discount only brings margin down to ~47.0%. So Sahara Retail could meaningfully increase discounts for French customers (e.g., by 5–15 percentage points) and stay well above the 20% margin floor.

## Q12: Is the VIP customer segment actually more profitable (higher margin) than standard customers?

```sql
WITH li AS (
  SELECT oi.order_id, o.customer_id, o.order_date, o.fx_rate_to_eur,
    (oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur AS net_rev_eur,
    (oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_cost * (1 - oi.line_discount_pct) * o.fx_rate_to_eur AS net_cost_eur
  FROM order_items oi
  JOIN orders o ON o.order_id = oi.order_id
  LEFT JOIN returns r ON r.order_item_id = oi.order_item_id
  WHERE o.status = 'completed'
),
seg AS (
  SELECT li.*, cs.segment
  FROM li
  LEFT JOIN customer_segments cs
    ON cs.customer_id = li.customer_id
    AND cs.valid_from <= li.order_date
    AND (cs.valid_to IS NULL OR li.order_date < cs.valid_to)
)
SELECT segment, ROUND(SUM(net_rev_eur), 2) AS revenue, ROUND(SUM(net_cost_eur), 2) AS cost,
  ROUND((SUM(net_rev_eur) - SUM(net_cost_eur)) / SUM(net_rev_eur), 4) AS margin
FROM seg
GROUP BY segment;
```

**Answer:** No — margin is essentially the same for both segments. Using each customer's segment as of the order date, standard customers had 54.88% margin (revenue €817,589.09) and VIP customers had 54.54% margin (revenue €56,185.50). VIP customers generate far less total revenue (VIP is a small segment) but are not meaningfully more profitable per euro sold than standard customers.

## Q13: Are orders that required split fulfillment (2+ shipments) more or less profitable on average than single-shipment orders?

```sql
WITH order_agg AS (
  SELECT o.order_id, o.fx_rate_to_eur,
    SUM((oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_price * (1 - oi.line_discount_pct)) * o.fx_rate_to_eur AS net_rev_eur,
    SUM((oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_cost * (1 - oi.line_discount_pct)) * o.fx_rate_to_eur AS net_cost_eur
  FROM orders o
  JOIN order_items oi ON oi.order_id = o.order_id
  LEFT JOIN returns r ON r.order_item_id = oi.order_item_id
  WHERE o.status = 'completed'
  GROUP BY o.order_id, o.fx_rate_to_eur
),
ship_counts AS (
  SELECT order_id, COUNT(*) AS n_shipments FROM shipments GROUP BY order_id
)
SELECT CASE WHEN COALESCE(sc.n_shipments,0) >= 2 THEN 'split (2+)' ELSE 'single/none' END AS fulfillment_type,
  COUNT(*) AS n_orders,
  ROUND(SUM(oa.net_rev_eur), 2) AS revenue,
  ROUND((SUM(oa.net_rev_eur) - SUM(oa.net_cost_eur)) / SUM(oa.net_rev_eur), 4) AS margin,
  ROUND(AVG(oa.net_rev_eur), 2) AS avg_order_revenue
FROM order_agg oa
LEFT JOIN ship_counts sc ON sc.order_id = oa.order_id
GROUP BY 1;
```

**Answer:** Split-fulfillment orders (2+ shipments) are marginally more profitable, not less: 55.08% margin vs. 54.79% for single/no-shipment orders — a small, likely not economically meaningful difference. Split orders also have a higher average order revenue (€480.24 vs €445.16), consistent with larger orders being more likely to require multiple shipments. Overall, profitability is essentially comparable between the two groups.

## Q14: Based on revenue and margin trends, does it look worthwhile for Sahara Retail to expand its Swiss operations relative to the Eurozone markets?

```sql
WITH li AS (
  SELECT oi.order_id, o.country, o.order_date, o.fx_rate_to_eur,
    (oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur AS net_rev_eur,
    (oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_cost * (1 - oi.line_discount_pct) * o.fx_rate_to_eur AS net_cost_eur
  FROM order_items oi
  JOIN orders o ON o.order_id = oi.order_id
  LEFT JOIN returns r ON r.order_item_id = oi.order_item_id
  WHERE o.status = 'completed'
)
SELECT CASE WHEN country = 'Switzerland' THEN 'Switzerland' ELSE 'Eurozone' END AS grp,
  ROUND(SUM(net_rev_eur), 2) AS revenue,
  ROUND((SUM(net_rev_eur) - SUM(net_cost_eur)) / SUM(net_rev_eur), 4) AS margin
FROM li
GROUP BY 1;
```

**Answer:** Not compellingly, based on this data. Switzerland's margin (54.57%) is essentially identical to the combined Eurozone markets' margin (54.92%) — no cost/margin advantage to expanding there. Switzerland's revenue is also much smaller (€158,781.01, ~18% of the total) than the combined Eurozone markets (€714,993.58), and quarterly figures (checked separately) show no accelerating growth trend for Switzerland relative to the Eurozone. On revenue scale and margin alone, there's no clear signal that Swiss expansion would outperform continuing to invest in the larger, equally profitable Eurozone markets; a stronger case would need external factors (market size, competition, growth potential) not present in this dataset.

## Q15: Would the elevated return activity in France in Q3 2025 be visible if we only looked at cancelled orders?

```sql
SELECT date_trunc('quarter', order_date) AS quarter, COUNT(*) AS cancelled_orders
FROM orders
WHERE country = 'France' AND status = 'cancelled'
GROUP BY 1
ORDER BY 1;
```

**Answer:** No. Cancelled orders in France are low and flat across the whole period — 6, 5, 3, 3, 2, 3 orders per quarter from 2024 Q3 through 2025 Q4 — with no spike in Q3 2025 (only 2 cancellations, actually the lowest quarter). This confirms the Q3 2025 return spike (45.87% of ordered quantity) is invisible in `orders.status`: it's driven entirely by partial, line-level returns recorded in the `returns` table, which don't change an order's status to cancelled. Looking only at cancelled orders would completely miss this issue.

## Q16: Identify the top 10 customers by net revenue across all four markets in 2025.

```sql
WITH li AS (
  SELECT o.customer_id, o.order_id,
    (oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur AS net_rev_eur
  FROM order_items oi
  JOIN orders o ON o.order_id = oi.order_id
  LEFT JOIN returns r ON r.order_item_id = oi.order_item_id
  WHERE o.status = 'completed' AND o.order_date BETWEEN '2025-01-01' AND '2025-12-31'
)
SELECT c.customer_id, c.name, c.country, ROUND(SUM(li.net_rev_eur), 2) AS net_revenue_eur
FROM li JOIN customers c ON c.customer_id = li.customer_id
GROUP BY c.customer_id, c.name, c.country
ORDER BY net_revenue_eur DESC
LIMIT 10;
```

**Answer:** Top 10 customers by 2025 net revenue (EUR):
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

## Q17: Identify which customers could be offered a 10% discount while keeping margin above 20%, across all markets.

```sql
WITH li AS (
  SELECT o.customer_id,
    (oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur AS net_rev_eur,
    (oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_cost * (1 - oi.line_discount_pct) * o.fx_rate_to_eur AS net_cost_eur
  FROM order_items oi
  JOIN orders o ON o.order_id = oi.order_id
  LEFT JOIN returns r ON r.order_item_id = oi.order_item_id
  WHERE o.status = 'completed'
),
cust AS (
  SELECT customer_id, SUM(net_rev_eur) AS revenue, SUM(net_cost_eur) AS cost
  FROM li GROUP BY customer_id
),
sim AS (
  SELECT customer_id, revenue, cost,
    (revenue - cost) / revenue AS current_margin,
    (revenue * 0.9 - cost) / (revenue * 0.9) AS margin_after_10pct_discount
  FROM cust
)
SELECT COUNT(*) AS total_customers,
  SUM(CASE WHEN margin_after_10pct_discount >= 0.20 THEN 1 ELSE 0 END) AS qualifying_customers,
  ROUND(MIN(margin_after_10pct_discount), 4) AS min_margin_after_discount
FROM sim;
```

**Answer:** All 300 customers in the dataset qualify. Applying a flat 10% discount to each customer's own historical revenue (cost unchanged) and recomputing margin per-customer, the lowest resulting margin across all 300 customers is 42.82% — comfortably above the 20% floor. Product-level margins are consistently high (~50–57%, see Q18) and fairly uniform across customers, so a 10% discount does not push any customer's margin close to the 20% threshold; a much deeper discount would be required before any customer became a risk.

## Q18: Rank product categories by margin, using the prices customers actually paid rather than current catalog prices.

```sql
WITH li AS (
  SELECT oi.product_id,
    (oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur AS net_rev_eur,
    (oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_cost * (1 - oi.line_discount_pct) * o.fx_rate_to_eur AS net_cost_eur
  FROM order_items oi
  JOIN orders o ON o.order_id = oi.order_id
  LEFT JOIN returns r ON r.order_item_id = oi.order_item_id
  WHERE o.status = 'completed'
)
SELECT p.category, ROUND(SUM(li.net_rev_eur), 2) AS revenue,
  ROUND((SUM(li.net_rev_eur) - SUM(li.net_cost_eur)) / SUM(li.net_rev_eur), 4) AS margin
FROM li JOIN products p ON p.product_id = li.product_id
GROUP BY p.category
ORDER BY margin DESC;
```

**Answer:** Ranked by margin (using order_items' transaction-time price/cost, not product_pricing catalog values): Kitchenware 56.71% (revenue €102,715.31), Accessories 55.46% (€198,652.05), Outdoor 54.75% (€294,136.47), Textiles 54.36% (€103,746.00), Home 54.23% (€145,261.10), Lighting 50.21% (€29,263.65, lowest margin and lowest revenue).

## Q19: If VIP-segment customers are more profitable, which standard customers look most similar to VIP customers on their purchase history, and could be considered for promotion?

```sql
-- First, check the premise (see also Q12): VIP vs standard margin and purchase-history profile
WITH cur_seg AS (
  SELECT customer_id, segment FROM customer_segments WHERE valid_to IS NULL
),
order_agg AS (
  SELECT o.customer_id, o.order_id,
    SUM((oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_price * (1 - oi.line_discount_pct)) * ANY_VALUE(o.fx_rate_to_eur) AS net_rev_eur
  FROM orders o
  JOIN order_items oi ON oi.order_id = o.order_id
  LEFT JOIN returns r ON r.order_item_id = oi.order_item_id
  WHERE o.status = 'completed'
  GROUP BY o.customer_id, o.order_id
),
cust_stats AS (
  SELECT customer_id, COUNT(*) AS order_count, SUM(net_rev_eur) AS total_revenue,
    AVG(net_rev_eur) AS avg_order_value
  FROM order_agg GROUP BY customer_id
),
vip_avg AS (
  SELECT AVG(stats.total_revenue) AS vip_avg_rev, AVG(stats.avg_order_value) AS vip_avg_aov
  FROM cust_stats stats JOIN cur_seg cs ON cs.customer_id = stats.customer_id WHERE cs.segment = 'VIP'
)
SELECT c.customer_id, c.name, c.country, stats.order_count,
  ROUND(stats.total_revenue, 2) AS total_revenue,
  ROUND(stats.avg_order_value, 2) AS avg_order_value,
  ROUND(SQRT(POWER(stats.avg_order_value - vip_avg.vip_avg_aov, 2)
            + POWER(stats.total_revenue - vip_avg.vip_avg_rev, 2) / 100), 2) AS similarity_dist
FROM cust_stats stats
JOIN cur_seg cs ON cs.customer_id = stats.customer_id
JOIN customers c ON c.customer_id = stats.customer_id
CROSS JOIN vip_avg
WHERE cs.segment = 'standard'
ORDER BY similarity_dist ASC
LIMIT 10;
```

**Answer:** First, the premise doesn't hold (per Q12): VIP customers are not actually more profitable than standard customers (54.54% vs 54.88% margin) — so there is no margin upside to "promoting" customers into VIP purely for profitability reasons. That said, answering the purchase-history similarity question as asked: using each customer's current segment, average purchase-history profile is order_count 5.94/total_revenue €2,562.47/AOV €426.58 for VIP vs order_count 6.50/total_revenue €2,954.39/AOV €456.72 for standard — the two groups already look quite similar on average. The standard customers whose purchase history (order count, total revenue, average order value) most closely resembles the average VIP profile are: John Peterson (France), Cynthia Wells (France), David Lopez (Belgium), Erika Terry (Germany), Rebecca Ramsey (France), Carmen Smith (Belgium), Michael Santos (France), Teresa Ramirez (France), Ronald Patel (Belgium), and Michael Burton (Belgium). Given VIP status doesn't confer a profitability edge in this data, any promotion decision should be based on other business goals (e.g., retention, loyalty perks) rather than expected margin gain.

## Q20: Build a market-by-market summary of revenue, margin, and return rate for 2025 that a regional manager could use to decide which market to prioritize fixing first.

```sql
WITH li AS (
  SELECT o.country, oi.quantity, COALESCE(r.quantity_returned,0) AS ret_qty,
    (oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur AS net_rev_eur,
    (oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_cost * (1 - oi.line_discount_pct) * o.fx_rate_to_eur AS net_cost_eur
  FROM order_items oi
  JOIN orders o ON o.order_id = oi.order_id
  LEFT JOIN returns r ON r.order_item_id = oi.order_item_id
  WHERE o.status = 'completed' AND o.order_date BETWEEN '2025-01-01' AND '2025-12-31'
)
SELECT country,
  ROUND(SUM(net_rev_eur), 2) AS revenue_eur,
  ROUND((SUM(net_rev_eur) - SUM(net_cost_eur)) / SUM(net_rev_eur), 4) AS margin,
  ROUND(SUM(ret_qty) * 1.0 / SUM(quantity), 4) AS return_rate
FROM li
GROUP BY country
ORDER BY revenue_eur DESC;
```

**Answer:** 2025 market summary (net revenue EUR, margin, return rate):
- France: €193,383.02 revenue, 55.00% margin, 14.24% return rate
- Germany: €168,154.88 revenue, 55.11% margin, 3.55% return rate
- Belgium: €101,911.36 revenue, 54.54% margin, 3.53% return rate
- Switzerland: €100,682.29 revenue, 54.85% margin, 3.35% return rate

All four markets have essentially the same (healthy) margin around 54.5–55.1%, so margin is not a differentiator. Revenue scale is led by France and Germany. The standout problem is France's return rate (14.24%), roughly 4x every other market — driven almost entirely by the Q3 2025 return spike (see Q6/Q10). A regional manager should prioritize France first: its revenue is currently the largest of the four, but its elevated return rate represents recovered/lost value and an operational or product-quality issue that the other three markets don't share.
