## Q1: What was total revenue (in EUR) for each of the four markets (France, Germany, Belgium, Switzerland) over the full data period?

```sql
SELECT country AS market, ROUND(SUM(net_revenue_eur), 2) AS total_revenue_eur
FROM line_detail
WHERE status = 'completed'
GROUP BY country
ORDER BY total_revenue_eur DESC;
```

**Answer:** France: €290,224.44; Germany: €258,889.36; Belgium: €165,879.78; Switzerland: €158,781.01 (net of returns, all currencies converted to EUR using each order's fx rate; completed orders only).

## Q2: What was the average order value in Q1 2025, and how does it compare to the average order value in Q4 2024?

```sql
WITH order_totals AS (
  SELECT order_id, order_date, SUM(net_revenue_eur) AS order_revenue_eur
  FROM line_detail
  WHERE status = 'completed'
  GROUP BY order_id, order_date
)
SELECT
  CASE
    WHEN order_date >= DATE '2025-01-01' AND order_date <= DATE '2025-03-31' THEN 'Q1 2025'
    WHEN order_date >= DATE '2024-10-01' AND order_date <= DATE '2024-12-31' THEN 'Q4 2024'
  END AS quarter,
  COUNT(*) AS n_orders,
  ROUND(AVG(order_revenue_eur), 2) AS avg_order_value_eur
FROM order_totals
WHERE (order_date >= DATE '2025-01-01' AND order_date <= DATE '2025-03-31')
   OR (order_date >= DATE '2024-10-01' AND order_date <= DATE '2024-12-31')
GROUP BY 1
ORDER BY 1;
```

**Answer:** Q1 2025 average order value was €472.35 (290 completed orders); Q4 2024 was €453.91 (340 completed orders). Q1 2025 is about €18.44 higher, an increase of roughly 4.1%.

## Q3: How many completed orders were placed in each quarter of 2025?

```sql
SELECT DATE_TRUNC('quarter', order_date) AS quarter, COUNT(*) AS n_completed_orders
FROM orders
WHERE status = 'completed'
  AND order_date >= DATE '2025-01-01' AND order_date <= DATE '2025-12-31'
GROUP BY 1
ORDER BY 1;
```

**Answer:** Q1 2025: 290 orders; Q2 2025: 308 orders; Q3 2025: 315 orders; Q4 2025: 362 orders.

## Q4: How many shipments were sent to Belgium in total?

```sql
SELECT COUNT(*) AS n_shipments_belgium
FROM shipments s
JOIN orders o ON o.order_id = s.order_id
WHERE o.country = 'Belgium';
```

**Answer:** 484 shipments were sent to Belgium.

## Q5: What is the total quantity of items ordered, broken down by product category?

```sql
SELECT p.category, SUM(oi.quantity) AS total_quantity_ordered
FROM order_items oi
JOIN products p ON p.product_id = oi.product_id
GROUP BY p.category
ORDER BY total_quantity_ordered DESC;
```

**Answer:** Outdoor: 2,988; Accessories: 2,259; Home: 1,871; Textiles: 1,336; Kitchenware: 970; Lighting: 563 (all orders, including cancelled, since the question asks for quantity "ordered" rather than sold/fulfilled).

## Q6: Why did net revenue in France decline in Q3 2025 compared to Q2 2025?

```sql
SELECT
  DATE_TRUNC('quarter', o.order_date) AS quarter,
  COUNT(DISTINCT o.order_id) AS n_orders,
  ROUND(SUM(oi.unit_price * (1 - oi.line_discount_pct) * oi.quantity * o.fx_rate_to_eur), 2) AS gross_revenue_eur,
  ROUND(SUM(oi.unit_price * (1 - oi.line_discount_pct) * (oi.quantity - COALESCE(r.qty_returned,0)) * o.fx_rate_to_eur), 2) AS net_revenue_eur,
  SUM(COALESCE(r.qty_returned,0)) AS units_returned,
  SUM(oi.quantity) AS units_ordered,
  ROUND(100.0 * SUM(COALESCE(r.qty_returned,0)) / NULLIF(SUM(oi.quantity),0), 2) AS return_rate_units_pct
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id
LEFT JOIN (SELECT order_item_id, SUM(quantity_returned) AS qty_returned FROM returns GROUP BY 1) r
  ON r.order_item_id = oi.order_item_id
WHERE o.status = 'completed' AND o.country = 'France'
  AND o.order_date >= DATE '2025-04-01' AND o.order_date <= DATE '2025-09-30'
GROUP BY 1
ORDER BY 1;
```

**Answer:** Gross (pre-return) revenue was essentially flat between Q2 2025 (€55,482) and Q3 2025 (€56,531) — orders placed and gross sales did not decline. However, net revenue fell sharply from €54,907 in Q2 to €29,998 in Q3 (a ~45% drop) because the return rate spiked from 1.3% of units in Q2 to 45.9% of units in Q3. This return surge is spread fairly evenly across all four return reasons (fulfillment_delay, changed_mind, damaged_in_transit, wrong_item — 64-76 units each), so it looks like a broad operational/fulfillment issue in France that quarter rather than one specific cause. The decline is a returns/anomaly effect, not a drop in underlying sales activity — it would be invisible if you only looked at gross bookings.

## Q7: What share of France's revenue in Q3 2025 came from customers who were VIP segment at the time of purchase?

```sql
SELECT
  cs.segment,
  ROUND(SUM(ld.net_revenue_eur), 2) AS net_revenue_eur,
  ROUND(100.0 * SUM(ld.net_revenue_eur) / SUM(SUM(ld.net_revenue_eur)) OVER (), 2) AS pct_of_total
FROM line_detail ld
JOIN customer_segments cs
  ON cs.customer_id = ld.customer_id
 AND ld.order_date >= cs.valid_from
 AND (cs.valid_to IS NULL OR ld.order_date < cs.valid_to)
WHERE ld.status = 'completed' AND ld.country = 'France'
  AND ld.order_date >= DATE '2025-07-01' AND ld.order_date <= DATE '2025-09-30'
GROUP BY 1
ORDER BY 1;
```

**Answer:** 9.81% of France's Q3 2025 net revenue (€2,941.76 of €29,997.81) came from customers who held VIP segment status at the time of purchase; the remaining 90.19% (€27,056.06) came from customers who were standard segment at the time of purchase. (Segment is time-varying, so this uses each customer's segment as of the order date, not their current segment.)

## Q8: Has average revenue per unit sold in the "Kitchenware" category changed over the data period, and why?

```sql
SELECT
  DATE_TRUNC('quarter', order_date) AS quarter,
  ROUND(SUM(net_revenue_eur) / NULLIF(SUM(qty_net),0), 2) AS avg_revenue_per_unit_eur,
  ROUND(AVG(unit_price), 2) AS avg_list_unit_price_at_order,
  ROUND(AVG(line_discount_pct)*100, 2) AS avg_discount_pct,
  SUM(qty_net) AS units_sold
FROM line_detail
WHERE status = 'completed' AND category = 'Kitchenware'
GROUP BY 1
ORDER BY 1;
```

**Answer:** Average net revenue per unit sold in Kitchenware fluctuated between roughly €112 and €126 across the six quarters (2024-Q3: €115.08, 2024-Q4: €112.33, 2025-Q1: €126.03, 2025-Q2: €121.66, 2025-Q3: €123.89, 2025-Q4: €113.06) — it rose into early/mid 2025 and then eased back down, with no sustained one-directional trend over the full period. The movement is driven mainly by which Kitchenware products (and their price points) sold in a given quarter (product mix), not by a broad repricing: of the 7 Kitchenware products, only 2 had catalog price changes during the period (both increases — product 10 from €142.05 to €165.63 in Aug 2024, and product 19 from €25.25 to €27.56 in May 2025), and average discount rates stayed roughly flat (4.2%-5.3%). This uses each order line's actual price paid at the time of purchase (order_items.unit_price), not current catalog pricing, since catalog prices have since changed for some products.

## Q9: Is average revenue per shipment declining for orders that required split fulfillment (more than one shipment)?

```sql
WITH order_rev AS (
  SELECT oi.order_id, o.order_date,
         SUM(oi.unit_price * (1 - oi.line_discount_pct) * (oi.quantity - COALESCE(r.qty_returned,0)) * o.fx_rate_to_eur) AS order_revenue_eur
  FROM order_items oi
  JOIN orders o ON o.order_id = oi.order_id
  LEFT JOIN (SELECT order_item_id, SUM(quantity_returned) AS qty_returned FROM returns GROUP BY 1) r
    ON r.order_item_id = oi.order_item_id
  WHERE o.status = 'completed'
  GROUP BY oi.order_id, o.order_date
),
shipment_counts AS (
  SELECT order_id, COUNT(*) AS n_shipments FROM shipments GROUP BY order_id
),
split_orders AS (
  SELECT o.order_id, o.order_date, o.order_revenue_eur / sc.n_shipments AS revenue_per_shipment
  FROM order_rev o
  JOIN shipment_counts sc ON sc.order_id = o.order_id
  WHERE sc.n_shipments >= 2
)
SELECT DATE_TRUNC('quarter', order_date) AS quarter,
       COUNT(*) AS n_split_orders,
       ROUND(AVG(revenue_per_shipment), 2) AS avg_revenue_per_shipment_eur
FROM split_orders
GROUP BY 1
ORDER BY 1;
```

**Answer:** No, there is no sustained decline. Average revenue per shipment for split-fulfillment orders (revenue attributed per order divided by that order's shipment count, to avoid double-counting order revenue across its multiple shipment rows) was €230.27 in 2024-Q3, dropped to €189.91 (Q4) and €179.17 (2025-Q1), then recovered to €217.46 (Q2), €196.44 (Q3), and €200.30 (Q4 2025). The series dips early and then fluctuates in a roughly €180-€220 band with no consistent downward trend across the full period.

## Q10: Which market has the highest return rate, and in which quarter does it peak?

```sql
WITH by_market AS (
  SELECT o.country,
         SUM(COALESCE(r.qty_returned,0)) AS units_returned,
         SUM(oi.quantity) AS units_ordered,
         ROUND(100.0*SUM(COALESCE(r.qty_returned,0))/NULLIF(SUM(oi.quantity),0),2) AS return_rate_pct
  FROM order_items oi
  JOIN orders o ON o.order_id = oi.order_id
  LEFT JOIN (SELECT order_item_id, SUM(quantity_returned) AS qty_returned FROM returns GROUP BY 1) r
    ON r.order_item_id = oi.order_item_id
  WHERE o.status = 'completed'
  GROUP BY 1
)
SELECT * FROM by_market ORDER BY return_rate_pct DESC;

-- peak quarter for the highest market (France)
SELECT DATE_TRUNC('quarter', o.order_date) AS quarter,
       SUM(COALESCE(r.qty_returned,0)) AS units_returned,
       SUM(oi.quantity) AS units_ordered,
       ROUND(100.0*SUM(COALESCE(r.qty_returned,0))/NULLIF(SUM(oi.quantity),0),2) AS return_rate_pct
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id
LEFT JOIN (SELECT order_item_id, SUM(quantity_returned) AS qty_returned FROM returns GROUP BY 1) r
  ON r.order_item_id = oi.order_item_id
WHERE o.status = 'completed' AND o.country = 'France'
GROUP BY 1
ORDER BY 1;
```

**Answer:** France has the highest return rate by units over the full period (10.86%, vs Switzerland 3.76%, Germany 3.45%, Belgium 2.93%). Within France, the return rate peaks sharply in Q3 2025 at 45.87% of units returned, far above any other quarter (next highest is Q4 2024 at 4.35%).

## Q11: Could Sahara Retail increase discounts for French customers without dropping overall margin below 20%?

```sql
WITH line_detail AS (
  SELECT oi.order_item_id, oi.order_id, o.order_date, o.country, o.status, o.fx_rate_to_eur,
         oi.unit_price, oi.unit_cost, oi.line_discount_pct, oi.quantity,
         COALESCE(r.qty_returned,0) AS qty_returned,
         oi.unit_price*(1-oi.line_discount_pct)*(oi.quantity-COALESCE(r.qty_returned,0))*o.fx_rate_to_eur AS net_revenue_eur,
         oi.unit_cost*(oi.quantity-COALESCE(r.qty_returned,0))*o.fx_rate_to_eur AS net_cost_eur,
         oi.unit_price*oi.quantity*o.fx_rate_to_eur AS list_revenue_eur
  FROM order_items oi
  JOIN orders o ON o.order_id = oi.order_id
  LEFT JOIN (SELECT order_item_id, SUM(quantity_returned) AS qty_returned FROM returns GROUP BY 1) r
    ON r.order_item_id = oi.order_item_id
)
SELECT
  ROUND(SUM(net_revenue_eur),2) AS net_revenue_eur,
  ROUND(SUM(net_cost_eur),2) AS net_cost_eur,
  ROUND(SUM(list_revenue_eur),2) AS list_revenue_eur,
  ROUND(100.0*(SUM(net_revenue_eur)-SUM(net_cost_eur))/SUM(net_revenue_eur),2) AS current_margin_pct,
  ROUND(100.0*(1-SUM(net_revenue_eur)/SUM(list_revenue_eur)),2) AS current_avg_discount_pct,
  ROUND(100.0*(1 - SUM(net_cost_eur)/(0.8*SUM(list_revenue_eur))),2) AS max_avg_discount_pct_for_20pct_margin
FROM line_detail
WHERE status = 'completed' AND country = 'France';
```

**Answer:** Yes, there is substantial room to increase discounts. France's current average effective discount (net of returns) is about 15.12%, giving an overall margin of 52.74% (net revenue EUR 290,224.44 vs. net cost EUR 137,156.51, against list/pre-discount revenue of EUR 341,921.75). Since unit cost is fixed regardless of discount, margin only drops to the 20% floor once the average discount reaches roughly 49.9%. So Sahara could roughly triple the average discount given to French customers (from ~15% to ~50%) before overall margin in France would fall below 20% -- there is a very large cushion, because underlying product margins in France are currently well above 20%.

## Q12: Is the VIP customer segment actually more profitable (higher margin) than standard customers?

```sql
WITH line_detail AS (
  SELECT oi.order_item_id, oi.order_id, o.order_date, o.customer_id, o.status, o.fx_rate_to_eur,
         oi.unit_price, oi.unit_cost, oi.line_discount_pct, oi.quantity,
         COALESCE(r.qty_returned,0) AS qty_returned,
         oi.unit_price*(1-oi.line_discount_pct)*(oi.quantity-COALESCE(r.qty_returned,0))*o.fx_rate_to_eur AS net_revenue_eur,
         oi.unit_cost*(oi.quantity-COALESCE(r.qty_returned,0))*o.fx_rate_to_eur AS net_cost_eur
  FROM order_items oi
  JOIN orders o ON o.order_id = oi.order_id
  LEFT JOIN (SELECT order_item_id, SUM(quantity_returned) AS qty_returned FROM returns GROUP BY 1) r
    ON r.order_item_id = oi.order_item_id
)
SELECT cs.segment,
  COUNT(DISTINCT ld.order_id) AS n_orders,
  ROUND(SUM(ld.net_revenue_eur),2) AS net_revenue_eur,
  ROUND(SUM(ld.net_cost_eur),2) AS net_cost_eur,
  ROUND(100.0*(SUM(ld.net_revenue_eur)-SUM(ld.net_cost_eur))/SUM(ld.net_revenue_eur),2) AS margin_pct
FROM line_detail ld
JOIN customer_segments cs
  ON cs.customer_id = ld.customer_id
 AND ld.order_date >= cs.valid_from
 AND (cs.valid_to IS NULL OR ld.order_date < cs.valid_to)
WHERE ld.status = 'completed'
GROUP BY 1
ORDER BY 1;
```

**Answer:** No. Using each customer's segment as of the order date (segment is time-varying), VIP-segment purchases had a margin of 52.03% while standard-segment purchases had a margin of 52.53% -- essentially the same, with standard customers marginally higher. VIP status in this data does not translate into higher per-sale profitability; it does not appear to be tied to deeper discounting or higher cost mix either way.

## Q13: Are orders that required split fulfillment (2+ shipments) more or less profitable on average than single-shipment orders?

```sql
WITH line_detail AS (
  SELECT oi.order_id, o.status, o.fx_rate_to_eur,
         oi.unit_price, oi.unit_cost, oi.line_discount_pct, oi.quantity,
         COALESCE(r.qty_returned,0) AS qty_returned,
         oi.unit_price*(1-oi.line_discount_pct)*(oi.quantity-COALESCE(r.qty_returned,0))*o.fx_rate_to_eur AS net_revenue_eur,
         oi.unit_cost*(oi.quantity-COALESCE(r.qty_returned,0))*o.fx_rate_to_eur AS net_cost_eur
  FROM order_items oi
  JOIN orders o ON o.order_id = oi.order_id
  LEFT JOIN (SELECT order_item_id, SUM(quantity_returned) AS qty_returned FROM returns GROUP BY 1) r
    ON r.order_item_id = oi.order_item_id
),
order_agg AS (
  SELECT order_id, SUM(net_revenue_eur) AS net_revenue, SUM(net_cost_eur) AS net_cost
  FROM line_detail
  WHERE status = 'completed'
  GROUP BY order_id
),
ship_counts AS (
  SELECT order_id, COUNT(*) AS n_shipments FROM shipments GROUP BY order_id
)
SELECT
  CASE WHEN sc.n_shipments >= 2 THEN 'split (2+)' ELSE 'single' END AS fulfillment_type,
  COUNT(*) AS n_orders,
  ROUND(AVG(oa.net_revenue),2) AS avg_order_revenue_eur,
  ROUND(AVG(oa.net_revenue - oa.net_cost),2) AS avg_order_margin_eur,
  ROUND(100.0*SUM(oa.net_revenue - oa.net_cost)/SUM(oa.net_revenue),2) AS margin_pct
FROM order_agg oa
JOIN ship_counts sc ON sc.order_id = oa.order_id
GROUP BY 1
ORDER BY 1;
```

**Answer:** Split-fulfillment orders are slightly more profitable, not less. Single-shipment orders (1,527 orders) average EUR 233.45 margin per order at a 52.44% margin rate, while split orders (404 orders, 2+ shipments) average EUR 253.09 margin per order at a 52.70% margin rate -- driven mainly by split orders having a somewhat higher average order value (EUR 480.24 vs EUR 445.16), which makes sense since larger/multi-item orders are more likely to require more than one shipment. There is no profitability penalty from split fulfillment in this data.

## Q14: Based on revenue and margin trends, does it look worthwhile for Sahara Retail to expand its Swiss operations relative to the Eurozone markets?

```sql
WITH line_detail AS (
  SELECT oi.order_id, o.order_date, o.country, o.status, o.fx_rate_to_eur,
         oi.unit_price, oi.unit_cost, oi.line_discount_pct, oi.quantity,
         COALESCE(r.qty_returned,0) AS qty_returned,
         oi.unit_price*(1-oi.line_discount_pct)*(oi.quantity-COALESCE(r.qty_returned,0))*o.fx_rate_to_eur AS net_revenue_eur,
         oi.unit_cost*(oi.quantity-COALESCE(r.qty_returned,0))*o.fx_rate_to_eur AS net_cost_eur
  FROM order_items oi
  JOIN orders o ON o.order_id = oi.order_id
  LEFT JOIN (SELECT order_item_id, SUM(quantity_returned) AS qty_returned FROM returns GROUP BY 1) r
    ON r.order_item_id = oi.order_item_id
)
SELECT DATE_TRUNC('quarter', order_date) AS quarter,
  CASE WHEN country = 'Switzerland' THEN 'Switzerland' ELSE 'Eurozone (FR/DE/BE)' END AS grp,
  ROUND(SUM(net_revenue_eur),2) AS net_revenue_eur,
  ROUND(100.0*(SUM(net_revenue_eur)-SUM(net_cost_eur))/SUM(net_revenue_eur),2) AS margin_pct
FROM line_detail
WHERE status = 'completed'
GROUP BY 1,2
ORDER BY 1,2;
```

**Answer:** Not obviously -- the data doesn't support prioritizing Swiss expansion over the Eurozone markets. Margins are essentially identical between Switzerland (~50-53% per quarter) and the combined Eurozone markets of France/Germany/Belgium (~52.5-52.8% per quarter), so there's no margin advantage to expanding in Switzerland. On revenue, Switzerland is a much smaller market (roughly EUR 23k-31k/quarter, about 18-20% the size of the Eurozone group) and its revenue trend is flat-to-slightly-declining (EUR 30,538.68 in 2024-Q3 down to EUR 27,104.79 in 2025-Q4), whereas the combined Eurozone markets grew over the same period (EUR 124,773.40 in 2024-Q3 to EUR 137,766.16 in 2025-Q4, despite the France return-driven dip in 2025-Q3). With comparable margins, a smaller base, and no clear growth trend, Switzerland does not currently look like the better market to prioritize for expansion relative to the Eurozone markets.

## Q15: Would the elevated return activity in France in Q3 2025 be visible if we only looked at cancelled orders?

```sql
SELECT DATE_TRUNC('quarter', order_date) AS quarter,
  status,
  COUNT(*) AS n_orders
FROM orders
WHERE country = 'France' AND order_date >= DATE '2025-04-01' AND order_date <= DATE '2025-09-30'
GROUP BY 1,2
ORDER BY 1,2;
```

**Answer:** No, it would not be visible. Looking only at order status, France's cancellation rate was low and essentially unchanged between Q2 2025 (3 cancelled of 110 orders, 2.73%) and Q3 2025 (2 cancelled of 119 orders, 1.68%) -- if anything cancellations went down slightly. Yet net revenue collapsed in Q3 2025 because of a spike in post-purchase returns (45.87% of units returned, vs 1.3% in Q2, per Q6), which is recorded separately in the `returns` table and does not change the order's `status` (returned orders still show as `completed`). This confirms the France Q3 2025 problem is a returns/fulfillment-quality issue that is completely invisible if you only monitor cancelled-order counts -- you have to look at the returns data (or net vs. gross revenue) to see it.

## Q16: Identify the top 10 customers by net revenue across all four markets in 2025.

```sql
WITH line_detail AS (
  SELECT oi.order_id, o.order_date, o.customer_id, o.status, o.fx_rate_to_eur,
         oi.unit_price, oi.unit_cost, oi.line_discount_pct, oi.quantity,
         COALESCE(r.qty_returned,0) AS qty_returned,
         oi.unit_price*(1-oi.line_discount_pct)*(oi.quantity-COALESCE(r.qty_returned,0))*o.fx_rate_to_eur AS net_revenue_eur
  FROM order_items oi
  JOIN orders o ON o.order_id = oi.order_id
  LEFT JOIN (SELECT order_item_id, SUM(quantity_returned) AS qty_returned FROM returns GROUP BY 1) r
    ON r.order_item_id = oi.order_item_id
)
SELECT ld.customer_id, c.name, c.country,
  ROUND(SUM(ld.net_revenue_eur),2) AS net_revenue_2025_eur
FROM line_detail ld
JOIN customers c ON c.customer_id = ld.customer_id
WHERE ld.status = 'completed' AND ld.order_date >= DATE '2025-01-01' AND ld.order_date <= DATE '2025-12-31'
GROUP BY 1,2,3
ORDER BY net_revenue_2025_eur DESC
LIMIT 10;
```

**Answer:** Top 10 customers by 2025 net revenue: 1) Richard Lawson (Switzerland) EUR 7,673.85; 2) Lawrence Perry (Germany) EUR 6,089.11; 3) Heidi Owen (Germany) EUR 5,674.09; 4) Jordan Bullock (France) EUR 5,089.79; 5) Thomas Romero (France) EUR 5,034.23; 6) Travis Wise (Germany) EUR 4,792.96; 7) Tanya Rogers (Germany) EUR 4,755.30; 8) Doris Hall (France) EUR 4,706.75; 9) Stephanie Gilbert (Germany) EUR 4,621.37; 10) John Boone (France) EUR 4,508.47.

## Q17: Identify which customers could be offered a 10% discount while keeping margin above 20%, across all markets.

```sql
WITH line_detail AS (
  SELECT oi.order_id, o.customer_id, o.status, o.fx_rate_to_eur,
         oi.unit_price, oi.unit_cost, oi.line_discount_pct, oi.quantity,
         COALESCE(r.qty_returned,0) AS qty_returned,
         oi.unit_price*(1-oi.line_discount_pct)*(oi.quantity-COALESCE(r.qty_returned,0))*o.fx_rate_to_eur AS net_revenue_eur,
         oi.unit_cost*(oi.quantity-COALESCE(r.qty_returned,0))*o.fx_rate_to_eur AS net_cost_eur
  FROM order_items oi
  JOIN orders o ON o.order_id = oi.order_id
  LEFT JOIN (SELECT order_item_id, SUM(quantity_returned) AS qty_returned FROM returns GROUP BY 1) r
    ON r.order_item_id = oi.order_item_id
),
cust_agg AS (
  SELECT ld.customer_id, c.name, c.country,
    SUM(ld.net_revenue_eur) AS net_revenue, SUM(ld.net_cost_eur) AS net_cost
  FROM line_detail ld
  JOIN customers c ON c.customer_id = ld.customer_id
  WHERE ld.status = 'completed'
  GROUP BY 1,2,3
)
SELECT
  COUNT(*) FILTER (WHERE net_revenue > 0 AND (net_revenue*0.9 - net_cost)/(net_revenue*0.9) >= 0.20) AS n_eligible_customers,
  COUNT(*) AS n_total_customers,
  ROUND(MIN((net_revenue*0.9 - net_cost)/(net_revenue*0.9))*100, 2) AS worst_margin_after_10pct_discount_pct
FROM cust_agg
WHERE net_revenue > 0;
```

**Answer:** All 300 customers across all four markets could be given a flat 10% discount on their historical purchases and still keep margin above 20% -- underlying margins are high enough (current per-customer margins mostly in the 45-55%+ range) that even the customer with the thinnest margin cushion (Laura Moreno, Germany, current margin 42.17%) would still sit at about 35.74% margin after a 10% discount, comfortably above the 20% floor. So the 20% margin constraint is not binding for a 10% discount at the customer level in this data; a more meaningful constraint would likely need a materially larger discount or a per-product-cost basis.

## Q18: Rank product categories by margin, using the prices customers actually paid rather than current catalog prices.

```sql
WITH line_detail AS (
  SELECT oi.order_id, o.status, o.fx_rate_to_eur, p.category,
         oi.unit_price, oi.unit_cost, oi.line_discount_pct, oi.quantity,
         COALESCE(r.qty_returned,0) AS qty_returned,
         oi.unit_price*(1-oi.line_discount_pct)*(oi.quantity-COALESCE(r.qty_returned,0))*o.fx_rate_to_eur AS net_revenue_eur,
         oi.unit_cost*(oi.quantity-COALESCE(r.qty_returned,0))*o.fx_rate_to_eur AS net_cost_eur
  FROM order_items oi
  JOIN orders o ON o.order_id = oi.order_id
  JOIN products p ON p.product_id = oi.product_id
  LEFT JOIN (SELECT order_item_id, SUM(quantity_returned) AS qty_returned FROM returns GROUP BY 1) r
    ON r.order_item_id = oi.order_item_id
)
SELECT category,
  ROUND(SUM(net_revenue_eur),2) AS net_revenue_eur,
  ROUND(SUM(net_cost_eur),2) AS net_cost_eur,
  ROUND(100.0*(SUM(net_revenue_eur)-SUM(net_cost_eur))/SUM(net_revenue_eur),2) AS margin_pct
FROM line_detail
WHERE status = 'completed'
GROUP BY category
ORDER BY margin_pct DESC;
```

**Answer:** Ranked by margin using each order line's actual `unit_price`/`unit_cost` at time of sale (not current catalog `product_pricing`): 1) Kitchenware 54.56%; 2) Accessories 53.10%; 3) Outdoor 52.44%; 4) Home 51.92%; 5) Textiles 51.72%; 6) Lighting 47.37% (lowest margin). This uses the price actually charged and cost actually incurred per line item, which can differ from current catalog prices since prices have changed over time for some products (see Q8), so recomputing margin from today's catalog price would misstate historical profitability.

## Q19: If VIP-segment customers are more profitable, which standard customers look most similar to VIP customers on their purchase history, and could be considered for promotion?

```sql
WITH line_detail AS (
  SELECT oi.order_id, o.customer_id, o.status, o.fx_rate_to_eur,
         oi.unit_price, oi.unit_cost, oi.line_discount_pct, oi.quantity,
         COALESCE(r.qty_returned,0) AS qty_returned,
         oi.unit_price*(1-oi.line_discount_pct)*(oi.quantity-COALESCE(r.qty_returned,0))*o.fx_rate_to_eur AS net_revenue_eur
  FROM order_items oi
  JOIN orders o ON o.order_id = oi.order_id
  LEFT JOIN (SELECT order_item_id, SUM(quantity_returned) AS qty_returned FROM returns GROUP BY 1) r
    ON r.order_item_id = oi.order_item_id
),
order_agg AS (
  SELECT order_id, customer_id, SUM(net_revenue_eur) AS order_revenue
  FROM line_detail
  WHERE status = 'completed'
  GROUP BY 1,2
),
profile AS (
  SELECT customer_id, COUNT(*) AS n_orders, SUM(order_revenue) AS total_net_revenue, AVG(order_revenue) AS avg_order_value
  FROM order_agg
  GROUP BY customer_id
),
cur_segment AS (
  SELECT customer_id, segment FROM customer_segments WHERE valid_to IS NULL
)
SELECT cs.segment, ROUND(AVG(p.n_orders),2) AS avg_n_orders,
  ROUND(AVG(p.total_net_revenue),2) AS avg_total_net_revenue,
  ROUND(AVG(p.avg_order_value),2) AS avg_order_value
FROM profile p
LEFT JOIN cur_segment cs ON cs.customer_id = p.customer_id
GROUP BY 1;
```

**Answer:** The premise doesn't hold, so promotion on profitability grounds isn't well-supported by the data. Q12 already showed VIP purchases are not more profitable (margin) than standard purchases. Looking at purchase-behavior profiles by current segment (the most recent row per customer in `customer_segments`) confirms this further: VIP customers actually average slightly *fewer* orders (5.94 vs 6.50), *lower* total net revenue (EUR 2,562.47 vs EUR 2,954.39), and *lower* average order value (EUR 426.58 vs EUR 456.72) than standard customers. In other words, "VIP" in this dataset is not associated with higher spend, order frequency, or margin -- it does not behave like a typical rewards/spend tier. A nearest-centroid similarity match on order count, total revenue, and average order value (normalized) identifies standard customers such as customer_id 100 (John Peterson, France), 81 (Cynthia Wells, France), 279 (David Lopez, Belgium), 59 (Erika Terry, Germany), and 76 (Rebecca Ramsey, France) as closest to the average VIP profile -- but since that VIP profile isn't more profitable or higher-spending, matching standard customers to it would not be a sound basis for promotion. Before promoting customers, it would be worth first understanding what actually drives current VIP assignment, since it does not appear to be purchase value in this data.

## Q20: Build a market-by-market summary of revenue, margin, and return rate for 2025 that a regional manager could use to decide which market to prioritize fixing first.

```sql
WITH line_detail AS (
  SELECT oi.order_id, o.order_date, o.country, o.status, o.fx_rate_to_eur,
         oi.unit_price, oi.unit_cost, oi.line_discount_pct, oi.quantity,
         COALESCE(r.qty_returned,0) AS qty_returned,
         oi.unit_price*(1-oi.line_discount_pct)*(oi.quantity-COALESCE(r.qty_returned,0))*o.fx_rate_to_eur AS net_revenue_eur,
         oi.unit_cost*(oi.quantity-COALESCE(r.qty_returned,0))*o.fx_rate_to_eur AS net_cost_eur
  FROM order_items oi
  JOIN orders o ON o.order_id = oi.order_id
  LEFT JOIN (SELECT order_item_id, SUM(quantity_returned) AS qty_returned FROM returns GROUP BY 1) r
    ON r.order_item_id = oi.order_item_id
)
SELECT country,
  ROUND(SUM(net_revenue_eur),2) AS net_revenue_eur,
  ROUND(100.0*(SUM(net_revenue_eur)-SUM(net_cost_eur))/SUM(net_revenue_eur),2) AS margin_pct,
  SUM(qty_returned) AS units_returned,
  SUM(quantity) AS units_ordered,
  ROUND(100.0*SUM(qty_returned)/SUM(quantity),2) AS return_rate_pct
FROM line_detail
WHERE status = 'completed' AND order_date >= DATE '2025-01-01' AND order_date <= DATE '2025-12-31'
GROUP BY country
ORDER BY net_revenue_eur DESC;
```

**Answer:** 2025 market summary (completed orders, net of returns, EUR): France -- revenue EUR 193,383.02, margin 52.80%, return rate 14.24% (329 of 2,310 units); Germany -- revenue EUR 168,154.88, margin 52.71%, return rate 3.55% (64 of 1,803 units); Belgium -- revenue EUR 101,911.36, margin 52.15%, return rate 3.53% (39 of 1,106 units); Switzerland -- revenue EUR 100,682.29, margin 52.52%, return rate 3.35% (37 of 1,103 units). Margins are nearly identical across all four markets (~52-53%), so margin alone doesn't distinguish them. The standout is return rate: France's 14.24% return rate is roughly 4x every other market, entirely driven by the Q3 2025 return spike (see Q6/Q10/Q15). Despite still being the largest market by revenue, France is the clear candidate to prioritize for fixing -- its return/fulfillment issue is actively eroding net revenue and, if it recurs or persists, poses the biggest risk to the business's largest market.
