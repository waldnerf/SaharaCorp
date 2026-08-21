# Policy: Attribute Orders to the Customer's Segment At Time of Order

Customer segment (standard vs. VIP) is not a fixed customer attribute — it
changes over time as customers grow their purchase history and value
(`customer_segments` is a point-in-time history table, one row per segment
period per customer). When attributing an order's revenue, margin, or
count to a segment, always use the segment that was in effect on the
order's date, not the customer's current or most recent segment.

**Why this matters:** Sahara Retail's `grow_vip_segment` priority (see
`context/company.yaml`) tracks how much revenue comes from VIP customers.
If a customer who is VIP *today* had their historical orders — placed back
when they were still a standard customer — retroactively counted as VIP
revenue, VIP performance would be systematically overstated, and the
metric would stop reflecting the actual value VIP customers delivered at
the time. It would also make it impossible to see the causal story
(customers becoming more valuable as they're promoted to VIP) because past
and present segment would be conflated.

This is the same failure mode as recognizing revenue at today's price
instead of the price paid (see `pricing_snapshot_policy.md`) — a snapshot
table exists specifically so that a fact can be correctly attributed to
the state of the world at the time the fact occurred, not the state of the
world now.

**Practical rule:** to attribute an order to a segment, join
`customer_segments` on `customer_id` and filter to the row where
`valid_from <= order_date AND (valid_to IS NULL OR order_date < valid_to)`.
Do not join on `customer_id` alone, and do not filter to
`valid_to IS NULL` (the customer's *current* segment) when the question is
about historical orders. This matches the `customer_segments` dataset's
`ai_context` in `semantic/retail.ossie.yaml`.
