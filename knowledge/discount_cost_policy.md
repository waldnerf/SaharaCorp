# Policy: Discounts Apply to Cost, Not Just Revenue

When a line item is sold at a discount, the discount reduces the price the
customer pays. It does not change the unit cost the business paid to acquire
or produce that item — but for margin reporting, Sahara Retail's finance
team treats the discounted line as if cost were reduced proportionally too.

This is a deliberate accounting convention, not a data artifact: margin is
defined as profitability of the *transaction actually recorded*, and
finance books discounted sales on a matched revenue/cost basis so that
`margin = (revenue - net_cost) / revenue` stays a meaningful ratio at the
line-item grain. If cost were left undiscounted while revenue was
discounted, every discounted line would show artificially depressed margin
in a way that doesn't reflect any real change in unit economics — it would
just reflect discount depth.

**Practical rule:** any time you compute cost for a margin calculation,
apply the same `(1 - line_discount_pct)` factor used for revenue. Do not
compute `net_cost` from `unit_cost * quantity` alone.

**Why this matters:** Phase 1 of this lab found that Conditions A (schema
only) and B (+ glossary) both independently omitted this discount factor
from cost, understating margin by roughly 2.2 percentage points and
flipping a category margin ranking (see `evals/results/comparison.md`,
Q18). Condition C (Ossie semantic model) got this right because the
`net_cost` metric definition encodes the discount factor explicitly — see
`semantic/retail.ossie.yaml`, metric `net_cost`. This document exists so
that Condition D (Ossie without knowledge would already have gotten this
right via the metric expression) and, more importantly, any condition that
relies on plain-language policy rather than a machine-readable metric
definition, has access to the *reasoning* behind the convention — not just
the formula.
