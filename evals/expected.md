# Expected Answers

Ground truth for all 20 questions in `evals/questions.md`, derived by running
`python -m scripts.verify_expected` against `data/retail.duckdb`. Every SQL
query below is transcribed verbatim from that script's output — none of
these answers were hand-typed or estimated.

All queries net returned quantity at the line-item grain, apply the line
discount, convert to EUR via `fx_rate_to_eur`, and (where relevant) filter
to `status = 'completed'` — i.e. they use the *correct* trap-resolving
definitions, independent of what any experiment condition's agent produces.

---

## Q1 — Total revenue by market (full period)

```sql
SELECT o.country, ROUND(SUM((oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_price * (1-oi.line_discount_pct) * o.fx_rate_to_eur),2) AS revenue_eur
FROM order_items oi JOIN orders o ON o.order_id=oi.order_id
LEFT JOIN returns r ON r.order_item_id=oi.order_item_id
WHERE o.status='completed' GROUP BY 1 ORDER BY 1
```
**Answer:** Belgium €165,879.78 · France €290,224.44 · Germany €258,889.36 · Switzerland €158,781.01

## Q2 — Average order value: Q1 2025 vs Q4 2024

**Answer:** Q4-2024: €453.91 (340 orders) · Q1-2025: €472.35 (290 orders) — AOV rose ~4%.

## Q3 — Completed orders per quarter, 2025

**Answer:** Q1: 290 · Q2: 308 · Q3: 315 · Q4: 362

## Q4 — Total shipments to Belgium

**Answer:** 464

## Q5 — Total quantity ordered by category

**Answer:** Outdoor 2,988 · Accessories 2,259 · Home 1,871 · Textiles 1,336 · Kitchenware 970 · Lighting 563

## Q6 — Why did France net revenue decline in Q3 2025 vs Q2 2025?

**Answer:** Net revenue fell from €54,907.00 (Q2-2025) to €29,997.81 (Q3-2025) — a ~45% drop. The return rate over the same period jumped from 1.26% to 45.87%. The decline is a returns spike, not a demand drop — gross order volume did not fall proportionally (see Q3/Q15).

## Q7 — Share of France Q3-2025 revenue from VIP-at-time-of-purchase customers

**Answer:** VIP: €8,505.99 (9.46%) · standard: €81,416.76 (90.54%)

## Q8 — Kitchenware avg unit price paid, by quarter

**Answer:** 2024-Q3: €120.78 (79 lines) · 2024-Q4: €118.07 (83) · 2025-Q1: €131.70 (56) · 2025-Q2: €131.01 (89) · 2025-Q3: €131.15 (83) · 2025-Q4: €117.07 (96). Price paid rose ~9% between 2024-Q4 and 2025-Q1 (consistent with a mid-period price increase for at least one Kitchenware product), then fell back in 2025-Q4.

## Q9 — Avg revenue per shipment: multi vs single shipment orders

**Answer:** multi-shipment: €193.06/shipment · single-shipment: €447.29/shipment. Multi-shipment orders show materially lower revenue per shipment — a naive query joining `orders → shipments → order_items` would inflate the "multi" figure by double/triple-counting line items per shipment (Trap 5).

## Q10 — Highest return rate, market/quarter

**Answer:** France, 2025-Q3: 45.87% (highest by a wide margin). Next highest: Germany 2025-Q2 (5.68%), Switzerland 2024-Q4 (4.92%).

## Q11 — Could France discounts increase without margin dropping below 20%?

**Answer:** France: revenue €290,224.44, cost €130,665.71, margin 54.98%, average existing line discount 4.9%. Margin has ~35 percentage points of headroom above the 20% floor — yes, there is substantial room to increase discounts before margin would be at risk, provided the discount doesn't also change the France return-rate dynamic.

## Q12 — Is VIP segment more profitable (margin) than standard?

**Answer:** VIP margin: 54.39% (revenue €171,497.57, cost €78,224.91). Standard margin: 54.88% (revenue €2,489,280.76, cost €1,123,194.15). Margins are nearly identical — VIP customers are **not** meaingfully more profitable on margin in this dataset, though they may still be more valuable on other dimensions (order frequency, retention).

## Q13 — Multi-shipment vs single-shipment order profitability (margin)

**Answer:** multi-shipment: 55.02% margin (287 orders) · single-shipment: 54.83% margin (1,644 orders). Margins are essentially the same — split fulfillment does not materially affect margin, even though it materially affects revenue-per-shipment (Q9).

## Q14 — Swiss vs Eurozone revenue/margin trend

**Answer:** Eurozone: 2024 €251,544.32 (54.89% margin) → 2025 €463,449.26 (54.94% margin). Switzerland: 2024 €58,098.72 (54.09% margin) → 2025 €100,682.29 (54.85% margin). Both grew at a similar rate year-over-year with comparable, converging margins — no strong evidence either way that Switzerland is under- or over-performing the Eurozone markets.

## Q15 — Would the France Q3-2025 return spike show up via cancelled-order status alone?

**Answer:** No. France cancelled-order counts: anomaly quarter 2 of 119 orders (1.7%) vs other quarters 20 of 581 orders (3.4%) — the cancellation rate in the anomaly quarter is actually *lower* than the baseline, not higher. The return spike is invisible to any query that only filters on `orders.status`; it only appears once `returns.quantity_returned` is netted at the line-item grain (Trap 3, directly demonstrated).

## Q16 — Top 10 customers by net revenue, 2025

**Answer:** customer_id 61 (€7,673.85), 176 (€6,089.11), 227 (€5,674.09), 185 (€5,089.79), 121 (€5,034.23), 244 (€4,792.96), 277 (€4,755.30), 106 (€4,706.75), 60 (€4,621.37), 170 (€4,508.47)

## Q17 — Customers who could take a 10% discount and stay above 20% margin

**Answer:** 300 of 300 customers (all of them) — baseline margins across the customer base (~55%) leave enough headroom that a further 10% price cut keeps every customer above the 20% margin floor, assuming cost is unaffected by the discount.

## Q18 — Product categories ranked by margin (price actually paid)

**Answer:** Kitchenware 56.71% · Accessories 55.46% · Outdoor 54.75% · Textiles 54.36% · Home 54.23% · Lighting 50.21% (lowest)

## Q19 — Standard customers most similar to VIP purchase profile

**Answer:** Nearest standard customers to the VIP average profile (6 orders, ~€427 AOV): customer_id 100, 81, 279, 59, 76, 33, 129, 152, 27, 110 (ranked by distance, closest first).

## Q20 — 2025 market summary: revenue, margin, return rate

**Answer:**

| Market | Revenue (EUR) | Margin | Return rate |
|---|---|---|---|
| Belgium | €101,911.36 | 54.54% | 3.53% |
| France | €193,383.02 | 55.00% | 14.24% |
| Germany | €168,154.88 | 55.11% | 3.55% |
| Switzerland | €100,682.29 | 54.85% | 3.35% |

France stands out only on return rate (14.24% vs ~3.5% elsewhere) — margin and revenue are broadly in line with the other markets. This is the single highest-impact fix: addressing France's return rate (driven by the Q3-2025 spike) would recover meaningfully more revenue than any pricing or discount lever elsewhere.
