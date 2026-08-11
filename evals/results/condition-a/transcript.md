# Transcript: Sahara Retail Data Questions

General notes on methodology (applies throughout):
- "Revenue" figures are computed from `order_items` (quantity x unit_price x (1 - line_discount_pct)), which records the price actually paid on that order — not the current catalog price in `product_price_history`.
- All monetary figures are converted to EUR using `orders.fx_rate_to_eur` (Swiss orders are in CHF and must be multiplied by this rate; EUR orders have a rate of 1.0000).
- Unless a question is explicitly about cancellations, calculations are restricted to `orders.status = 'completed'`.
- "Net revenue" = gross line revenue minus the value of returned units, using `returns.quantity_returned` (returns are partial — at the order-item level, not full-order) joined to `order_items` via `order_item_id`.
- "Margin" = (net revenue - cost of kept units) / net revenue, where cost = quantity x unit_cost (net of returned units), converted to EUR via the order's fx rate.
- Customer segment (standard/VIP) is a slowly-changing dimension in `customer_segment_history` (`valid_from`/`valid_to`); when segment-at-purchase-time matters, the order date is matched against the applicable validity interval rather than using the customer's current segment.
- `shipments` is one-to-many per order; shipment counts/revenue-per-shipment are computed by aggregating shipments per order first, then joining back to order-level revenue, to avoid fan-out duplication of revenue.

---

## Q1: What was total revenue (in EUR) for each of the four markets (France, Germany, Belgium, Switzerland) over the full data period?

```sql
SELECT o.country AS market,
       ROUND(SUM(oi.quantity * oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur), 2) AS revenue_eur
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.status = 'completed'
GROUP BY 1
ORDER BY 2 DESC;
```

**Answer:** Over the full data period (2024-07-01 to 2025-12-31), total revenue for completed orders, converted to EUR, was: France €325,547.80, Germany €267,834.12, Belgium €170,895.14, Switzerland €165,332.25. France is the largest market, roughly double Belgium or Switzerland; note Swiss order amounts are recorded in CHF and were converted to EUR using each order's fx rate, since taking the CHF face values at par would have overstated Swiss revenue.

---

## Q2: What was the average order value in Q1 2025, and how does it compare to the average order value in Q4 2024?

```sql
WITH order_val AS (
  SELECT o.order_id, o.order_date,
         SUM(oi.quantity * oi.unit_price * (1 - oi.line_discount_pct) * o.fx_rate_to_eur) AS order_value_eur
  FROM orders o JOIN order_items oi ON oi.order_id = o.order_id
  WHERE o.status = 'completed'
  GROUP BY 1,2
)
SELECT
  CASE WHEN order_date BETWEEN '2025-01-01' AND '2025-03-31' THEN 'Q1_2025'
       WHEN order_date BETWEEN '2024-10-01' AND '2024-12-31' THEN 'Q4_2024' END AS period,
  ROUND(AVG(order_value_eur),2) AS avg_order_value, COUNT(*) n
FROM order_val
WHERE order_date BETWEEN '2025-01-01' AND '2025-03-31'
   OR order_date BETWEEN '2024-10-01' AND '2024-12-31'
GROUP BY 1;
```

**Answer:** Average order value was €490.88 in Q1 2025 (290 orders) versus €474.87 in Q4 2024 (340 orders) — an increase of about €16.01, or roughly 3.4%. (Values use the price actually paid on each order line, not current catalog prices, since historical orders should be valued at the price in effect when they were placed.)

---

## Q3: How many completed orders were placed in each quarter of 2025?

```sql
SELECT date_trunc('quarter', order_date) AS quarter, COUNT(*) n
FROM orders
WHERE status = 'completed' AND order_date BETWEEN '2025-01-01' AND '2025-12-31'
GROUP BY 1 ORDER BY 1;
```

**Answer:** Q1 2025: 290 completed orders; Q2 2025: 308; Q3 2025: 315; Q4 2025: 362. Order volume grew steadily through the year, with the biggest jump in Q4.

---

## Q4: How many shipments were sent to Belgium in total?

```sql
SELECT COUNT(*)
FROM shipments s
JOIN orders o ON s.order_id = o.order_id
WHERE o.country = 'Belgium';
```

**Answer:** 464 shipments in total were associated with Belgian orders (444 of these were for completed orders and 20 for orders that were later cancelled).

---

## Q5: What is the total quantity of items ordered, broken down by product category?

```sql
SELECT p.category, SUM(oi.quantity) qty
FROM order_items oi
JOIN products p ON oi.product_id = p.product_id
JOIN orders o ON oi.order_id = o.order_id
WHERE o.status = 'completed'
GROUP BY 1 ORDER BY 2 DESC;
```

**Answer:** Total units ordered (completed orders) by category: Outdoor 2,886; Accessories 2,188; Home 1,794; Textiles 1,293; Kitchenware 940; Lighting 550.

---

## Q6: Why did net revenue in France decline in Q3 2025 compared to Q2 2025?

```sql
WITH line AS (
  SELECT o.order_id, o.order_date, o.country, o.fx_rate_to_eur,
         oi.order_item_id, oi.quantity, oi.unit_price, oi.unit_cost, oi.line_discount_pct,
         COALESCE(r.ret_qty,0) AS ret_qty
  FROM orders o
  JOIN order_items oi ON oi.order_id = o.order_id
  LEFT JOIN (SELECT order_item_id, SUM(quantity_returned) ret_qty FROM returns GROUP BY 1) r
    ON r.order_item_id = oi.order_item_id
  WHERE o.status = 'completed' AND o.country = 'France'
)
SELECT date_trunc('quarter', order_date) AS q,
  COUNT(DISTINCT order_id) n_orders,
  ROUND(SUM(quantity*unit_price*(1-line_discount_pct)*fx_rate_to_eur),2) gross_rev,
  ROUND(SUM(ret_qty*unit_price*(1-line_discount_pct)*fx_rate_to_eur),2) returned_value,
  ROUND(SUM((quantity-ret_qty)*unit_price*(1-line_discount_pct)*fx_rate_to_eur),2) net_rev,
  SUM(quantity) total_qty, SUM(ret_qty) total_ret_qty,
  ROUND(SUM(ret_qty)*1.0/SUM(quantity),4) return_rate_qty
FROM line
WHERE order_date BETWEEN '2025-01-01' AND '2025-12-31'
GROUP BY 1 ORDER BY 1;
```

**Answer:** France's net revenue fell from €54,907 in Q2 2025 to €29,998 in Q3 2025 — but this was not driven by fewer sales: gross (pre-return) revenue actually rose slightly (€55,482 → €56,531), order count rose (107 → 117), and units ordered rose (556 → 606). The decline was driven almost entirely by a spike in returns: returned value jumped from €575 (Q2) to €26,533 (Q3), and the quantity-based return rate jumped from 1.3% to 45.9%. The elevated returns were spread roughly evenly across all four recorded reasons (damaged_in_transit, changed_mind, fulfillment_delay, wrong_item), so it is a broad-based return-rate anomaly for France in Q3 2025 rather than one specific cause.

---

## Q7: What share of France's revenue in Q3 2025 came from customers who were VIP segment at the time of purchase?

```sql
WITH line AS (
  SELECT o.order_id, o.order_date, o.customer_id, o.fx_rate_to_eur,
         oi.quantity, oi.unit_price, oi.line_discount_pct
  FROM orders o JOIN order_items oi ON oi.order_id = o.order_id
  WHERE o.status = 'completed' AND o.country = 'France'
    AND o.order_date BETWEEN '2025-07-01' AND '2025-09-30'
),
seg AS (
  SELECT l.*, csh.segment
  FROM line l
  JOIN customer_segment_history csh ON csh.customer_id = l.customer_id
    AND l.order_date >= csh.valid_from AND (csh.valid_to IS NULL OR l.order_date < csh.valid_to)
)
SELECT segment, ROUND(SUM(quantity*unit_price*(1-line_discount_pct)*fx_rate_to_eur),2) rev
FROM seg GROUP BY 1;
```

**Answer:** VIP-segment customers (based on their segment as of the purchase date, not their current segment) accounted for about 7.3% of France's Q3 2025 revenue (€4,112 of €56,531 total), with standard customers accounting for the remaining 92.7%.

---

## Q8: Has average revenue per unit sold in the "Kitchenware" category changed over the data period, and why?

```sql
SELECT date_trunc('quarter', o.order_date) q,
  SUM(oi.quantity) qty,
  ROUND(SUM(oi.quantity*oi.unit_price*(1-oi.line_discount_pct)*o.fx_rate_to_eur)/SUM(oi.quantity),2) avg_rev_per_unit,
  ROUND(AVG(oi.line_discount_pct),4) avg_discount
FROM orders o JOIN order_items oi ON oi.order_id = o.order_id
JOIN products p ON oi.product_id = p.product_id
WHERE o.status = 'completed' AND p.category = 'Kitchenware'
GROUP BY 1 ORDER BY 1;

-- catalog price history for Kitchenware products, for context
SELECT p.product_id, pph.unit_price, pph.valid_from, pph.valid_to
FROM products p JOIN product_price_history pph ON p.product_id = pph.product_id
WHERE p.category = 'Kitchenware'
ORDER BY p.product_id, pph.valid_from;
```

**Answer:** Average revenue per unit sold in Kitchenware has fluctuated in a fairly narrow band, roughly €113–€127, with no sustained upward or downward trend: €114.13 (2024-Q3) → €114.07 (2024-Q4) → €127.00 (2025-Q1) → €121.22 (2025-Q2) → €122.84 (2025-Q3) → €113.03 (2025-Q4). Only two Kitchenware products had catalog price increases during the period (product 10: €142.05→€165.63 in Aug 2024; product 19: €25.25→€27.56 in May 2025), and these are too small/isolated to explain the quarter-to-quarter swings. The fluctuation is better explained by which specific products/quantities sold each quarter (product mix) and small variation in discounting, rather than a systematic pricing trend.

---

## Q9: Is average revenue per shipment declining for orders that required split fulfillment (more than one shipment)?

```sql
WITH order_rev AS (
  SELECT o.order_id, o.order_date,
    SUM(oi.quantity*oi.unit_price*(1-oi.line_discount_pct)*o.fx_rate_to_eur) rev
  FROM orders o JOIN order_items oi ON oi.order_id = o.order_id
  WHERE o.status = 'completed'
  GROUP BY 1,2
),
ship_count AS (
  SELECT order_id, COUNT(*) n_ship FROM shipments GROUP BY 1
)
SELECT date_trunc('quarter', r.order_date) q,
  COUNT(*) n_orders,
  ROUND(AVG(r.rev / s.n_ship),2) avg_rev_per_shipment
FROM order_rev r JOIN ship_count s ON r.order_id = s.order_id
WHERE s.n_ship > 1
GROUP BY 1 ORDER BY 1;
```

**Answer:** No — there isn't a sustained decline. Average revenue per shipment for split-fulfillment orders (order revenue divided by that order's number of shipments, to avoid double-counting revenue across shipment rows) moved: €230.30 (2024-Q3) → €217.61 → €205.38 → €191.65 (2025-Q2, the low point) → €201.97 → €232.69 (2025-Q4). It dipped through late 2024/early 2025 but recovered fully by Q4 2025, ending slightly above where it started. For comparison, single-shipment orders average about €475.77 per shipment (unsurprising since split orders divide the same revenue across more shipments).

---

## Q10: Which market has the highest return rate, and in which quarter does it peak?

```sql
WITH line AS (
  SELECT o.order_id, o.country, o.order_date, oi.order_item_id, oi.quantity,
    COALESCE(r.ret_qty,0) ret_qty
  FROM orders o JOIN order_items oi ON oi.order_id = o.order_id
  LEFT JOIN (SELECT order_item_id, SUM(quantity_returned) ret_qty FROM returns GROUP BY 1) r
    ON r.order_item_id = oi.order_item_id
  WHERE o.status = 'completed'
)
SELECT country, ROUND(SUM(ret_qty)*1.0/SUM(quantity),4) return_rate
FROM line GROUP BY 1 ORDER BY 2 DESC;

-- by market and quarter, to find the peak
SELECT country, date_trunc('quarter', order_date) q,
  ROUND(SUM(ret_qty)*1.0/SUM(quantity),4) return_rate
FROM line GROUP BY 1,2 ORDER BY 1,2;
```

**Answer:** France has the highest overall return rate at 10.9% of units returned (versus 3.8% Switzerland, 3.5% Germany, 2.9% Belgium). France's return rate peaks dramatically in Q3 2025 at 45.9% of units — far above any other market/quarter combination (the next-highest quarterly rate anywhere is Germany Q2 2025 at 5.7%).

---

## Q11: Could Sahara Retail increase discounts for French customers without dropping overall margin below 20%?

```sql
WITH line AS (
  SELECT o.order_id, o.country, oi.order_item_id, oi.quantity, oi.unit_price, oi.unit_cost, oi.line_discount_pct,
    o.fx_rate_to_eur, COALESCE(r.ret_qty,0) ret_qty
  FROM orders o JOIN order_items oi ON oi.order_id = o.order_id
  LEFT JOIN (SELECT order_item_id, SUM(quantity_returned) ret_qty FROM returns GROUP BY 1) r
    ON r.order_item_id = oi.order_item_id
  WHERE o.status = 'completed'
)
SELECT country,
  ROUND(SUM((quantity-ret_qty)*unit_price*(1-line_discount_pct)*fx_rate_to_eur),2) net_rev,
  ROUND(SUM((quantity-ret_qty)*unit_cost*fx_rate_to_eur),2) tot_cost,
  ROUND((SUM((quantity-ret_qty)*unit_price*(1-line_discount_pct)*fx_rate_to_eur)
       - SUM((quantity-ret_qty)*unit_cost*fx_rate_to_eur))
      / SUM((quantity-ret_qty)*unit_price*(1-line_discount_pct)*fx_rate_to_eur),4) margin
FROM line GROUP BY 1;
```

**Answer:** Yes, comfortably. Overall margin across all markets is currently about 52.5% (net revenue €873,775 vs. cost €415,055), and France's own margin (52.7%) is in line with the other markets (Germany 52.7%, Switzerland 52.0%, Belgium 52.2%) — there is no single market dragging down the average. Working out the breakeven point: even if France's revenue were cut all the way to zero (an extreme, illustrative case), the remaining markets alone would still deliver about 28.9% margin — still above the 20% floor. So there is very large headroom (tens of percentage points) to increase French discounts before overall company margin would be at risk; the 20% floor is not a binding constraint at anything like realistic discount levels.

---

## Q12: Is the VIP customer segment actually more profitable (higher margin) than standard customers?

```sql
WITH line AS (
  SELECT o.order_id, o.order_date, o.customer_id, oi.order_item_id, oi.quantity, oi.unit_price, oi.unit_cost,
    oi.line_discount_pct, o.fx_rate_to_eur, COALESCE(r.ret_qty,0) ret_qty
  FROM orders o JOIN order_items oi ON oi.order_id = o.order_id
  LEFT JOIN (SELECT order_item_id, SUM(quantity_returned) ret_qty FROM returns GROUP BY 1) r
    ON r.order_item_id = oi.order_item_id
  WHERE o.status = 'completed'
),
seg AS (
  SELECT l.*, csh.segment
  FROM line l JOIN customer_segment_history csh ON csh.customer_id = l.customer_id
    AND l.order_date >= csh.valid_from AND (csh.valid_to IS NULL OR l.order_date < csh.valid_to)
)
SELECT segment,
  ROUND(SUM((quantity-ret_qty)*unit_price*(1-line_discount_pct)*fx_rate_to_eur),2) net_rev,
  ROUND(SUM((quantity-ret_qty)*unit_cost*fx_rate_to_eur),2) tot_cost,
  ROUND((SUM((quantity-ret_qty)*unit_price*(1-line_discount_pct)*fx_rate_to_eur)
       - SUM((quantity-ret_qty)*unit_cost*fx_rate_to_eur))
      / SUM((quantity-ret_qty)*unit_price*(1-line_discount_pct)*fx_rate_to_eur),4) margin,
  ROUND(AVG(line_discount_pct),4) avg_disc
FROM seg GROUP BY 1;
```

**Answer:** No, not meaningfully. Using each customer's segment as of the purchase date, standard customers have a margin of 52.5% and VIP customers 52.0% — essentially the same (VIP is actually marginally lower), and average line-level discount rates are nearly identical (~5.0%) for both groups. There's no evidence in this data that VIP status is associated with higher profitability.

---

## Q13: Are orders that required split fulfillment (2+ shipments) more or less profitable on average than single-shipment orders?

```sql
WITH line AS (
  SELECT o.order_id, oi.order_item_id, oi.quantity, oi.unit_price, oi.unit_cost, oi.line_discount_pct,
    o.fx_rate_to_eur, COALESCE(r.ret_qty,0) ret_qty
  FROM orders o JOIN order_items oi ON oi.order_id = o.order_id
  LEFT JOIN (SELECT order_item_id, SUM(quantity_returned) ret_qty FROM returns GROUP BY 1) r
    ON r.order_item_id = oi.order_item_id
  WHERE o.status = 'completed'
),
order_agg AS (
  SELECT order_id,
    SUM((quantity-ret_qty)*unit_price*(1-line_discount_pct)*fx_rate_to_eur) net_rev,
    SUM((quantity-ret_qty)*unit_cost*fx_rate_to_eur) tot_cost
  FROM line GROUP BY 1
),
ship_count AS (
  SELECT order_id, COUNT(*) n_ship FROM shipments GROUP BY 1
)
SELECT (s.n_ship>1) split, COUNT(*) n_orders,
  ROUND(AVG(o.net_rev),2) avg_net_rev,
  ROUND(AVG((o.net_rev-o.tot_cost)/NULLIF(o.net_rev,0)),4) avg_margin
FROM order_agg o JOIN ship_count s ON o.order_id = s.order_id
GROUP BY 1;
```

**Answer:** About the same. Split-fulfillment orders (2+ shipments) average 52.1% margin versus 52.2% for single-shipment orders — essentially no difference. Split orders do have a higher average order value (€482 vs. €447), which makes sense since larger orders are more likely to need multiple shipments, but requiring split fulfillment itself is not associated with lower (or higher) profitability per order.

---

## Q14: Based on revenue and margin trends, does it look worthwhile for Sahara Retail to expand its Swiss operations relative to the Eurozone markets?

```sql
WITH line AS (
  SELECT o.order_id, o.country, o.order_date, oi.order_item_id, oi.quantity, oi.unit_price, oi.unit_cost,
    oi.line_discount_pct, o.fx_rate_to_eur, COALESCE(r.ret_qty,0) ret_qty
  FROM orders o JOIN order_items oi ON oi.order_id = o.order_id
  LEFT JOIN (SELECT order_item_id, SUM(quantity_returned) ret_qty FROM returns GROUP BY 1) r
    ON r.order_item_id = oi.order_item_id
  WHERE o.status = 'completed'
)
SELECT country, date_trunc('quarter', order_date) q,
  ROUND(SUM((quantity-ret_qty)*unit_price*(1-line_discount_pct)*fx_rate_to_eur),2) net_rev,
  ROUND((SUM((quantity-ret_qty)*unit_price*(1-line_discount_pct)*fx_rate_to_eur)
       - SUM((quantity-ret_qty)*unit_cost*fx_rate_to_eur))
      / SUM((quantity-ret_qty)*unit_price*(1-line_discount_pct)*fx_rate_to_eur),4) margin
FROM line
WHERE country IN ('Switzerland','France','Germany','Belgium')
GROUP BY 1,2 ORDER BY 1,2;
```

**Answer:** No, the data doesn't support prioritizing Swiss expansion. In EUR terms (correctly converted from CHF), Switzerland is the smallest of the four markets and its quarterly net revenue is flat-to-slightly-declining over the period (€30,539 in 2024-Q3 down to roughly €22,850–€27,105 across 2025, with no clear recovery trend). Its margin (~52%) is essentially the same as every other market — no premium that would offset the weaker growth. France and Germany are both larger and show more resilient or growing revenue (e.g., France ends the period at its highest quarterly revenue, €63,872 in Q4 2025). On revenue trend and margin alone, the Eurozone markets look like the better investment priority.

---

## Q15: Would the elevated return activity in France in Q3 2025 be visible if we only looked at cancelled orders?

```sql
SELECT o.status, COUNT(*) n_orders
FROM orders o
WHERE o.country = 'France' AND o.order_date BETWEEN '2025-07-01' AND '2025-09-30'
GROUP BY 1;

SELECT o.status, COUNT(DISTINCT oi.order_id) orders_with_returns, SUM(r.quantity_returned) qty_ret
FROM returns r
JOIN order_items oi ON r.order_item_id = oi.order_item_id
JOIN orders o ON oi.order_id = o.order_id
WHERE o.country = 'France' AND o.order_date BETWEEN '2025-07-01' AND '2025-09-30'
GROUP BY 1;
```

**Answer:** No, it would be almost invisible. Of France's Q3 2025 orders, only 2 were cancelled (versus 117 completed), and those 2 cancelled orders account for just 10 returned units. The return spike (278 returned units across 99 completed orders) sits almost entirely within completed orders. Looking only at cancelled orders would miss the anomaly essentially entirely.

---

## Q16: Identify the top 10 customers by net revenue across all four markets in 2025.

```sql
WITH line AS (
  SELECT o.order_id, o.customer_id, o.order_date, oi.order_item_id, oi.quantity, oi.unit_price, oi.line_discount_pct,
    o.fx_rate_to_eur, COALESCE(r.ret_qty,0) ret_qty
  FROM orders o JOIN order_items oi ON oi.order_id = o.order_id
  LEFT JOIN (SELECT order_item_id, SUM(quantity_returned) ret_qty FROM returns GROUP BY 1) r
    ON r.order_item_id = oi.order_item_id
  WHERE o.status = 'completed' AND o.order_date BETWEEN '2025-01-01' AND '2025-12-31'
)
SELECT l.customer_id, c.name, c.country,
  ROUND(SUM((quantity-ret_qty)*unit_price*(1-line_discount_pct)*fx_rate_to_eur),2) net_rev
FROM line l JOIN customers c ON l.customer_id = c.customer_id
GROUP BY 1,2,3 ORDER BY 4 DESC LIMIT 10;
```

**Answer:** Top 10 customers by 2025 net revenue: 1) Richard Lawson (Switzerland) €7,673.85; 2) Lawrence Perry (Germany) €6,089.11; 3) Heidi Owen (Germany) €5,674.09; 4) Jordan Bullock (France) €5,089.79; 5) Thomas Romero (France) €5,034.23; 6) Travis Wise (Germany) €4,792.96; 7) Tanya Rogers (Germany) €4,755.30; 8) Doris Hall (France) €4,706.75; 9) Stephanie Gilbert (Germany) €4,621.37; 10) John Boone (France) €4,508.47.

---

## Q17: Identify which customers could be offered a 10% discount while keeping margin above 20%, across all markets.

```sql
WITH line AS (
  SELECT o.order_id, o.customer_id, oi.order_item_id, oi.quantity, oi.unit_price, oi.unit_cost, oi.line_discount_pct,
    o.fx_rate_to_eur, COALESCE(r.ret_qty,0) ret_qty
  FROM orders o JOIN order_items oi ON oi.order_id = o.order_id
  LEFT JOIN (SELECT order_item_id, SUM(quantity_returned) ret_qty FROM returns GROUP BY 1) r
    ON r.order_item_id = oi.order_item_id
  WHERE o.status = 'completed'
),
cust AS (
  SELECT customer_id,
    SUM((quantity-ret_qty)*unit_price*(1-line_discount_pct)*fx_rate_to_eur) net_rev,
    SUM((quantity-ret_qty)*unit_cost*fx_rate_to_eur) tot_cost
  FROM line GROUP BY 1
)
-- a further 10% price cut turns current margin m into 1-(1-m)/0.9, which is >=20% exactly when m >= 28%
SELECT count(*) FROM cust WHERE net_rev>0 AND (net_rev-tot_cost)/net_rev >= 0.28;

SELECT min((net_rev-tot_cost)/net_rev), max((net_rev-tot_cost)/net_rev), avg((net_rev-tot_cost)/net_rev), count(*)
FROM cust WHERE net_rev>0;
```

**Answer:** All 300 customers qualify. A 10% additional discount on top of current pricing keeps a customer's margin above 20% as long as their current margin is at least 28% (since a 10% revenue cut with unchanged cost turns margin m into 1-(1-m)/0.9). Every customer in the dataset already has a margin between 42.2% and 57.6% (average 52.3%), all comfortably above that 28% threshold — so a 10% discount could be extended to the entire customer base across all markets without breaching the 20% margin floor.

---

## Q18: Rank product categories by margin, using the prices customers actually paid rather than current catalog prices.

```sql
WITH line AS (
  SELECT o.order_id, p.category, oi.order_item_id, oi.quantity, oi.unit_price, oi.unit_cost, oi.line_discount_pct,
    o.fx_rate_to_eur, COALESCE(r.ret_qty,0) ret_qty
  FROM orders o JOIN order_items oi ON oi.order_id = o.order_id
  JOIN products p ON oi.product_id = p.product_id
  LEFT JOIN (SELECT order_item_id, SUM(quantity_returned) ret_qty FROM returns GROUP BY 1) r
    ON r.order_item_id = oi.order_item_id
  WHERE o.status = 'completed'
)
SELECT category,
  ROUND((SUM((quantity-ret_qty)*unit_price*(1-line_discount_pct)*fx_rate_to_eur)
       - SUM((quantity-ret_qty)*unit_cost*fx_rate_to_eur))
      / SUM((quantity-ret_qty)*unit_price*(1-line_discount_pct)*fx_rate_to_eur),4) margin
FROM line GROUP BY 1 ORDER BY 2 DESC;
```

**Answer:** Ranked by margin (using actual transaction prices, i.e. `order_items.unit_price`, not the current catalog price in `product_price_history`): 1) Kitchenware 54.6%; 2) Accessories 53.1%; 3) Outdoor 52.4%; 4) Home 51.9%; 5) Textiles 51.7%; 6) Lighting 47.4%. Lighting is the clear laggard; the other five categories cluster fairly tightly between 51.7% and 54.6%.

---

## Q19: If VIP-segment customers are more profitable, which standard customers look most similar to VIP customers on their purchase history, and could be considered for promotion?

```sql
WITH line AS (
  SELECT o.order_id, o.customer_id, oi.order_item_id, oi.quantity, oi.unit_price, oi.line_discount_pct,
    o.fx_rate_to_eur, COALESCE(r.ret_qty,0) ret_qty
  FROM orders o JOIN order_items oi ON oi.order_id = o.order_id
  LEFT JOIN (SELECT order_item_id, SUM(quantity_returned) ret_qty FROM returns GROUP BY 1) r
    ON r.order_item_id = oi.order_item_id
  WHERE o.status = 'completed'
),
cust_orders AS (
  SELECT customer_id, order_id,
    SUM((quantity-ret_qty)*unit_price*(1-line_discount_pct)*fx_rate_to_eur) order_net_rev
  FROM line GROUP BY 1,2
),
cust AS (
  SELECT customer_id, COUNT(*) n_orders, ROUND(SUM(order_net_rev),2) total_net_rev,
    ROUND(AVG(order_net_rev),2) avg_order_value
  FROM cust_orders GROUP BY 1
),
cur_seg AS (
  SELECT customer_id, segment FROM customer_segment_history WHERE valid_to IS NULL
)
SELECT cs.segment, count(*), round(avg(c.total_net_rev),2), round(avg(c.avg_order_value),2), round(avg(c.n_orders),2)
FROM cust c JOIN cur_seg cs ON c.customer_id = cs.customer_id
GROUP BY 1;

-- top standard customers by total net revenue as the closest "VIP-like" analogues
SELECT c.customer_id, cu.name, c.total_net_rev, c.avg_order_value, c.n_orders
FROM cust c JOIN cur_seg cs ON c.customer_id = cs.customer_id
JOIN customers cu ON cu.customer_id = c.customer_id
WHERE cs.segment = 'standard'
ORDER BY c.total_net_rev DESC LIMIT 10;
```

**Answer:** The premise doesn't actually hold in this data (consistent with Q12): VIP customers are not more profitable than standard customers. In fact, on average, standard customers have slightly *higher* total net revenue (€2,954 vs. €2,562), average order value (€457 vs. €427), and order count (6.5 vs. 5.9) than VIP customers — the current VIP segment doesn't correspond to a distinctive high-value purchase pattern. So there's no behavioral basis to single out "VIP-like" standard customers for promotion based on profitability; most standard customers already resemble or exceed the VIP profile. If a purely revenue-based shortlist is still wanted, the standard customers who most resemble/exceed typical VIP purchase volumes are, by total net revenue: Richard Lawson (€9,770.76), Lawrence Perry (€7,389.96), Denise Weber (€7,037.70), Travis Wise (€6,641.50), Jordan Bullock (€6,414.16), Heidi Owen (€6,353.25), Thomas Romero (€5,923.27), Susan Bennett (€5,861.12), Sandra Williams (€5,828.58), and Paul Larsen (€5,678.48).

---

## Q20: Build a market-by-market summary of revenue, margin, and return rate for 2025 that a regional manager could use to decide which market to prioritize fixing first.

```sql
WITH line AS (
  SELECT o.order_id, o.country, oi.order_item_id, oi.quantity, oi.unit_price, oi.unit_cost, oi.line_discount_pct,
    o.fx_rate_to_eur, COALESCE(r.ret_qty,0) ret_qty
  FROM orders o JOIN order_items oi ON oi.order_id = o.order_id
  LEFT JOIN (SELECT order_item_id, SUM(quantity_returned) ret_qty FROM returns GROUP BY 1) r
    ON r.order_item_id = oi.order_item_id
  WHERE o.status = 'completed' AND o.order_date BETWEEN '2025-01-01' AND '2025-12-31'
)
SELECT country,
  ROUND(SUM((quantity-ret_qty)*unit_price*(1-line_discount_pct)*fx_rate_to_eur),2) net_rev,
  ROUND(SUM(quantity*unit_price*(1-line_discount_pct)*fx_rate_to_eur),2) gross_rev,
  ROUND((SUM((quantity-ret_qty)*unit_price*(1-line_discount_pct)*fx_rate_to_eur)
       - SUM((quantity-ret_qty)*unit_cost*fx_rate_to_eur))
      / SUM((quantity-ret_qty)*unit_price*(1-line_discount_pct)*fx_rate_to_eur),4) margin,
  ROUND(SUM(ret_qty)*1.0/SUM(quantity),4) return_rate_qty
FROM line GROUP BY 1 ORDER BY 2 DESC;
```

**Answer:** 2025 summary (EUR, completed orders):

| Market | Gross revenue | Net revenue | Margin | Return rate (units) |
|---|---|---|---|---|
| France | €224,880 | €193,383 | 52.8% | 14.2% |
| Germany | €174,017 | €168,155 | 52.7% | 3.6% |
| Belgium | €105,582 | €101,911 | 52.2% | 3.5% |
| Switzerland | €104,629 | €100,682 | 52.5% | 3.4% |

All four markets have essentially the same margin (~52-53%), so margin is not a differentiator. France is by far the largest market by revenue but also stands out with a return rate roughly 4x every other market (14.2% vs. ~3.5%), driven almost entirely by the Q3 2025 return spike identified above (Q6/Q10). France is the clear market to prioritize fixing first: it has the most revenue at stake and the only significant operational anomaly (returns), while the other three markets look comparably healthy and stable.
