# Eval Questions

20 questions across 4 levels. Data period: 2024-07-01 through 2025-12-31.

This file is one of the files shown to Claude Code in all three conditions
(A, B, C) — it must stand alone as a plain-language question set, with no
table/column names or hints about the underlying schema.

## Trap coverage map (for scoring — not part of the agent-visible task)

| Question | Traps exercised |
|---|---|
| 1 | 4 (multi-currency) |
| 2 | 1 (snapshot pricing) |
| 6 | 3 (partial returns / anomaly) |
| 7 | 2 (SCD segment) |
| 8 | 1 (snapshot pricing) |
| 9 | 5 (shipment fan-out) |
| 10 | 3 (partial returns) |
| 11 | 1, 3 |
| 12 | 2 |
| 13 | 5 |
| 14 | 4 |
| 15 | 3 |
| 16 | 1, 3, 4 |
| 17 | 1, 3, 4 |
| 18 | 1 |
| 19 | 2 |
| 20 | 1, 2, 3, 4, 5 (all) |

---

## Level 1 — Data

1. What was total revenue (in EUR) for each of the four markets (France, Germany, Belgium, Switzerland) over the full data period?
2. What was the average order value in Q1 2025, and how does it compare to the average order value in Q4 2024?
3. How many completed orders were placed in each quarter of 2025?
4. How many shipments were sent to Belgium in total?
5. What is the total quantity of items ordered, broken down by product category?

## Level 2 — Business ("why")

6. Why did net revenue in France decline in Q3 2025 compared to Q2 2025?
7. What share of France's revenue in Q3 2025 came from customers who were VIP segment at the time of purchase?
8. Has average revenue per unit sold in the "Kitchenware" category changed over the data period, and why?
9. Is average revenue per shipment declining for orders that required split fulfillment (more than one shipment)?
10. Which market has the highest return rate, and in which quarter does it peak?

## Level 3 — Policy

11. Could Sahara Retail increase discounts for French customers without dropping overall margin below 20%?
12. Is the VIP customer segment actually more profitable (higher margin) than standard customers?
13. Are orders that required split fulfillment (2+ shipments) more or less profitable on average than single-shipment orders?
14. Based on revenue and margin trends, does it look worthwhile for Sahara Retail to expand its Swiss operations relative to the Eurozone markets?
15. Would the elevated return activity in France in Q3 2025 be visible if we only looked at cancelled orders?

## Level 4 — Action / optimization

16. Identify the top 10 customers by net revenue across all four markets in 2025.
17. Identify which customers could be offered a 10% discount while keeping margin above 20%, across all markets.
18. Rank product categories by margin, using the prices customers actually paid rather than current catalog prices.
19. If VIP-segment customers are more profitable, which standard customers look most similar to VIP customers on their purchase history, and could be considered for promotion?
20. Build a market-by-market summary of revenue, margin, and return rate for 2025 that a regional manager could use to decide which market to prioritize fixing first.
