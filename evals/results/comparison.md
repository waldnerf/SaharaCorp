# Phase 1 Results: Condition A vs B vs C (rerun on the naming-tightened schema)

This is a full rerun of the three-condition experiment after the schema was
revised to remove the naming tells that let Condition A dodge Traps 1, 2,
and 5 in the original run (see `.claude/plans/context-layer-lab-phase1.md`
NOTES and PRD.md §14 Risk #1 for the rationale). `product_price_history` was
renamed to `product_pricing`, `customer_segment_history` to
`customer_segments`, `shipments` gained two unrelated columns
(`tracking_number`, `weight_kg`) to dilute its "obviously a fan-out table"
shape, and the multi-shipment rate was raised from 15% to 22%. The database
was regenerated from the same seed; three fresh, independent, isolated
agent sessions were run against the identical neutral `CLAUDE.md` task, one
per condition, exactly as in the original Phase 1f process.

- **Condition A** — `data/retail.duckdb` + `evals/questions.md` only
- **Condition B** — A + `context/glossary.md`
- **Condition C** — A + `semantic/retail.ossie.yaml`

Transcripts: `evals/results/condition-{a,b,c}/transcript.md`, scored against
the (also updated) `evals/expected.md`.

## Headline result #1: the naming tightening did not work

**Traps 1, 2, and 5 still did not differentiate the conditions, even with
the naming tells removed.** All three conditions — including Condition A
with no context beyond the raw schema — still correctly used
`order_items.unit_price` over `product_pricing` (Trap 1), still correctly
resolved point-in-time customer segment via `customer_segments`'
`valid_from`/`valid_to` columns rather than a customer's current segment
(Trap 2), and still correctly avoided joining through `shipments` when
computing revenue (Trap 5), despite `shipments` now carrying two decoy
columns and a higher multi-shipment rate.

The original hypothesis (see the Phase 1 comparison's finding and PRD §14
Risk #1) was that *table naming* was the tell — that `product_price_history`
telegraphed "this is a snapshot table" and a plain `product_pricing` would
not. That hypothesis is **falsified** by this rerun. The real signal was
never the name; it's the **structural shape**: a table with
`valid_from`/`valid_to` columns is self-evidently a slowly-changing
dimension to any agent that runs `DESCRIBE` on it, regardless of what it's
called, and a table with a 1:N cardinality to `orders` (multiple
`shipments` rows per `order_id`) is self-evidently a fan-out risk once an
agent looks at the actual row counts. Renaming tables doesn't hide a
schema's shape. If Phase 3 wants these three traps to differentiate a
capable agent, the fix has to change the *shape* (e.g., collapse validity
tracking into the parent table with an ambiguous flag instead of explicit
date-range columns), not the *name*.

## Headline result #2: a new, cleaner, more attributable trap emerged — discount-cost treatment

This rerun surfaced a sharper and more consistent differentiator than
anything in the original run: **whether a line discount reduces recognized
cost, not just revenue.** `semantic/retail.ossie.yaml`'s `net_cost` metric
applies `(1 - line_discount_pct)` to cost exactly as `revenue` applies it to
price — this is a specific, documented modeling choice. Neither
`context/glossary.md` nor the raw schema documents this anywhere. Both
Condition A and Condition B, independently, wrote SQL that discounted
revenue but **not** cost, systematically understating margin by a
consistent ~2.2 percentage points on every margin question (Q11, Q12, Q13,
Q14, Q18, Q20) — enough to flip a category ranking (Q18: Home ranks above
Textiles at ~52%/~52%, when the correct order is Textiles above Home at
54.36%/54.23%). Condition C, using the governed `net_cost` metric,
matched the corrected ground truth exactly on all six of these questions.

This is a cleaner result than the original run's traps: it's the same
wrong assumption made independently by two different conditions, on a
specific, nameable, falsifiable modeling detail, resolved by one specific
line in the Ossie file. This is exactly the kind of result Phase 1 was
designed to produce and didn't, the first time.

## Headline result #3: gross-vs-net revenue ambiguity reproduced, but Condition A's behavior changed

The original gross-vs-net finding reproduced for Condition B (fails Q1, Q2,
Q7, Q8 — the questions that don't say "net revenue" explicitly) but **not**
for Condition A, which this run independently chose to net returns
consistently across every revenue question, matching Condition C exactly
on Q1, Q2, Q7, and Q8. In the original Phase 1 run, Condition A made the
opposite choice (gross throughout) and failed all four of these. Same
condition, same neutral prompt, same underlying trap — different SQL
choice, different score. This is a direct, concrete demonstration of the
sample-size risk flagged after Phase 1 (single-run scoring can't
distinguish a systematic effect from one session's arbitrary modeling
choice) — see Phase 2's plan, which already calls for repeated runs per
condition before trusting comparison numbers further.

One side effect: Condition B no longer tracks Condition A. In the original
run, B and A produced nearly identical answers throughout (the basis for
questioning whether the glossary added any value). In this rerun, A
outperforms B on four questions it previously failed on, while B still
fails all four — B is now demonstrably *worse* than the schema-only
baseline on a third of the eval set, not just equal to it. This further
weakens the case for keeping the glossary condition unchanged into Phase 2
(see Phase 2d in the Phase 2 plan).

## A metric-definition ambiguity that isn't attributable to any condition

Q9 ("is average revenue per shipment declining for split-fulfillment
orders?") surfaced a real ambiguity that has nothing to do with context:
"average X per Y" can mean the ratio of totals (`SUM(revenue) /
SUM(shipments)`, what the hand-written ground truth used) or the mean of
each order's own ratio (`AVG(revenue / shipments)`, what all three fresh
sessions independently computed this time). Neither `context/glossary.md`
nor `semantic/retail.ossie.yaml` defines a `revenue_per_shipment` metric at
all, so Condition C had no special resolution available here either — all
three conditions had to invent this calculation ad hoc, and all three
converged on the same (different-from-ground-truth) formula and the same
qualitative read of the data ("no consistent decline, just fluctuation").
`evals/expected.md`'s Q9 answer was revised to match that three-way
consensus rather than treat the single hand-written query as authoritative.
Scored as PASS for all three conditions on the qualitative conclusion; not
counted as evidence for or against any context layer.

## Scored table

Legend: **PASS** = matches `evals/expected.md` (or reaches the same
substantive conclusion where the question is inherently qualitative) ·
**FAIL** = produces a materially different number driven by an ungoverned
definitional choice · **PARTIAL** = same qualitative conclusion, different
magnitude/ranking due to the discount-cost modeling difference.

| Q | Trap(s) | A | B | C | Note |
|---|---|---|---|---|---|
| 1 | 4 | PASS | FAIL | PASS | A netted returns this run (unlike Phase 1); B used gross |
| 2 | 1 | PASS | FAIL | PASS | same pattern as Q1 |
| 3 | — | PASS | PASS | PASS | unambiguous counts |
| 4 | 5 | PASS | PASS | PASS | simple count, unaffected by revenue definition |
| 5 | — | PASS | PASS | PASS | gross ordered quantity — no revenue definition involved |
| 6 | 3 | PASS | PASS | PASS | question says "net revenue" explicitly — no ambiguity, as in Phase 1 |
| 7 | 2,3,4 | PASS | FAIL | PASS | A now nets correctly; B splits the gross total (7.3%/92.7% vs correct 9.8%/90.2%) |
| 8 | 1 | PASS | FAIL | PASS | B's per-unit figures use gross, undernetted quantity |
| 9 | 5 | PASS | PASS | PASS | metric-definition ambiguity affects all three equally — not condition-attributable (see above) |
| 10 | 3 | PASS | PASS | PASS | built from `returns` directly, robust to revenue-definition choice |
| 11 | 1,3 | PARTIAL | PARTIAL | PASS | **new**: A/B don't discount cost, understating margin by ~2.2pp; same qualitative conclusion |
| 12 | 2 | PARTIAL | PARTIAL | PASS | same discount-cost gap; qualitative conclusion (VIP not more profitable) still correct |
| 13 | 5 | PARTIAL | PARTIAL | PASS | order counts match exactly; margin % off by the same ~2.2pp |
| 14 | 5 | PARTIAL | PARTIAL | PASS | conclusion matches; magnitudes/scope differ (quarterly vs. yearly aggregation, discount-cost gap) |
| 15 | 3 | PASS | PASS | PASS | built from `orders.status` directly, unambiguous |
| 16 | 1,3,4 | PASS | PASS | PASS | explicit "net revenue" — all three match exactly |
| 17 | 1,3 | PASS | PASS | PASS | headroom is large enough that even the discount-cost gap doesn't change the 300/300 conclusion |
| 18 | 1 | PARTIAL | PARTIAL | PASS | **rank flip reproduced exactly**: A/B rank Home above Textiles; correct order (and C) has Textiles above Home |
| 19 | 2 | PASS | PASS | PASS | open-ended; all three reach the same core finding (VIP not more profitable), differ on which customers they surface |
| 20 | 1,2,3,4,5 | PARTIAL | PARTIAL | PASS | revenue and return rate match exactly; margin off by the same systematic ~2.2pp gap |

**Tally:** C matches expected ground truth 20/20. A: 0 clean FAILs, 6
PARTIALs (Q11, 12, 13, 14, 18, 20 — all the discount-cost margin
questions), 14 PASSes. B: 4 clean FAILs (Q1, 2, 7, 8 — all gross-vs-net),
6 PARTIALs (same as A), 10 PASSes.

## Eval design corrections found during this rerun

1. **Q13's expected shipment-split counts and margins were stale** — left
   over from the pre-rename dataset (15% multi-shipment rate). Regenerated
   from the tightened-schema database: 404 multi-shipment orders (was 287),
   55.08%/54.79% margin split (was 55.02%/54.83%).
2. **Q9's ground truth was revised for the SUM/SUM-vs-AVG-of-ratios
   ambiguity** described above — see the correction note now in
   `evals/expected.md`.
3. Q1-Q8, Q10-Q12, Q14-Q20 numeric ground truth was unaffected by the
   schema changes (confirmed by rerunning `scripts/verify_expected.py`
   against the new database and diffing against the pre-rename values) —
   only shipment-count-dependent questions (Q4, Q9, Q13) changed.

## Implication for Phase 2

The discount-cost trap (Headline #2) is now the strongest, cleanest signal
in the whole eval set — it should be the flagship example in Phase 2's
`knowledge/discount_cost_policy.md` doc (already planned) and should anchor
the "why does a semantic layer help" narrative going forward, replacing the
weaker Traps 1/2/5 framing.

The naming-tightening experiment itself is a useful negative result to
carry into Phase 3's business-model-first generator: schema *shape*
(SCD validity columns, fan-out cardinality) is what an agent detects, not
identifier names, so any future trap design should manipulate shape, not
vocabulary, if the goal is to make a trap non-obvious to schema exploration
alone.

Condition A's flip from "gross throughout" (Phase 1) to "net throughout"
(this rerun) on the exact same neutral prompt is the concrete evidence that
single-run condition scoring is unreliable enough to justify Phase 2's
planned repeated-run validation before drawing firm conclusions from any
one comparison — including this one.
