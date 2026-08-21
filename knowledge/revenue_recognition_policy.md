# Policy: Revenue Recognition Is Net, Not Gross

"Revenue" at Sahara Retail means **net revenue**: the value of what a
customer actually kept, at the price they actually paid, converted to EUR.
Three adjustments apply before a number should be reported as "revenue":

1. **Net of returns.** If a customer ordered 3 units and returned 1, revenue
   reflects 2 units. This applies at the order-line grain, using the
   `returns` table's `quantity_returned` — it does not depend on and is not
   visible from `orders.status`, which stays `"completed"` even when lines
   within the order were later returned.
2. **Net of discount.** Revenue reflects the price actually paid
   (`unit_price * (1 - line_discount_pct)`), not the undiscounted list
   price.
3. **Converted to EUR at transaction time.** Orders are placed in the
   customer's local currency; revenue is reported in EUR using the FX rate
   captured on the order's date, not a current or period-end rate.

**Why "net" and not "gross":** management's KPIs (revenue, margin,
return_rate — see `context/company.yaml`) are used to compare markets and
track the return-rate-reduction priority. A gross figure that ignores
returns would make a market with a returns problem look artificially
healthy — masking exactly the signal the business needs (see
`narrative_anchor` in `context/company.yaml`, the France Q3 2025
fulfillment-delay anomaly). Reporting gross revenue would hide that
anomaly entirely, since gross figures don't move when returns spike.

**Practical rule:** unless a question explicitly asks for a *gross* or
*pre-return* figure, "revenue" means net-of-returns, net-of-discount,
EUR-converted. This is the same definition as the `revenue` metric in
`semantic/retail.ossie.yaml`.

**Ambiguity note:** some question wording (e.g. "total revenue," "gross
sales") does not explicitly say "net" — this is intentional wording
ambiguity used to test whether the correct default is applied even when
not stated (see Phase 2's wording-variant questions). The default at
Sahara Retail is always net unless "gross" is stated explicitly.
