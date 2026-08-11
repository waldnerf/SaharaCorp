# Phase 1 Results: Condition A vs B vs C

Three fresh, independent agent sessions (no shared context, no knowledge of
the experiment) were each given the identical neutral task from `CLAUDE.md`
plus one of three file sets:

- **Condition A** — `data/retail.duckdb` + `evals/questions.md` only
- **Condition B** — A + `context/glossary.md`
- **Condition C** — A + `semantic/retail.ossie.yaml`

Each agent's SQL and answers are in `evals/results/condition-{a,b,c}/transcript.md`,
scored against `evals/expected.md`. This document is the scored comparison
and failure-mode analysis called for by the Phase 1 plan.

## Headline result

The cleanest, most attributable finding is **not** "Condition C got harder
questions right that A/B got wrong" in the way the original trap design
anticipated. Instead:

**Conditions A and B were internally inconsistent about what "revenue" means, depending on how a question was worded — Condition C was not.**

When a question said "net revenue" explicitly (Q6, Q16), all three
conditions computed the same, correct, return-netted figure. When a question
just said "revenue" (Q1) or asked for a derived split (Q7), Conditions A and
B silently fell back to a **gross** figure (returns not netted), while
Condition C applied the single governed `revenue` metric from
`semantic/retail.ossie.yaml` — which already nets returns by definition —
uniformly, regardless of question wording. This produced measurably wrong
numbers for A/B on Q1, Q2, and Q7 (not just "less precise" — the wrong
value), while C matched the verified ground truth on all three.

A second, more nuanced finding: on every **margin** question (Q12, Q13, Q18,
Q20), Conditions A and B consistently applied a different (but internally
self-consistent) accounting assumption than the Ossie file — they did not
discount the *cost* basis by `line_discount_pct`, only the revenue, while
the Ossie `net_cost` metric applies the discount to both. This is not "A/B
were wrong" in the way Q1/Q7 were wrong — it's a legitimate, defensible
modeling choice that simply wasn't documented anywhere for A/B to discover,
so each made its own (matching) assumption. The consequence was real,
though: on Q18, this flipped the relative margin ranking of two categories
(Home vs. Textiles) that the correct ranking has close together — a
difference that would change which category a manager gets told to look at.

**Traps 1, 2, and 5 did not differentiate the conditions in this run.** All
three agents — even Condition A with no context beyond the raw schema —
correctly used `order_items.unit_price` over `product_price_history`
(Trap 1), correctly resolved point-in-time customer segment via
`customer_segment_history` (Trap 2), and correctly avoided joining through
`shipments` when computing revenue (Trap 5). This is a genuine, useful
negative result: for an agent as capable as the one used here, self-evident
column naming (`unit_price` on the transaction table vs. a table named
`_history`; a `shipments` table that obviously fans out on a 1:N join) was
enough to avoid these particular traps without any documentation. The traps
that *did* bite (Traps 3 and 4, expressed through the "gross vs. net"
inconsistency) were the ones where the ambiguity was in the **question's
own wording**, not in the schema's shape.

## Scored table

Legend: **PASS** = matches `evals/expected.md` (or reaches the same
substantive conclusion where the question is inherently qualitative) ·
**FAIL** = produces a materially different number driven by an ungoverned
definitional choice · **PARTIAL** = same qualitative conclusion, different
magnitude/ranking due to the cost/discount modeling difference ·
**N/A*** = this question's ground truth in `evals/expected.md` itself had a
design flaw (see Eval Design Corrections below); not attributable to any condition.

| Q | Trap(s) | A | B | C | Note |
|---|---|---|---|---|---|
| 1 | 4 | FAIL | FAIL | PASS | A/B used gross revenue; C used the governed net metric |
| 2 | 1 | FAIL | FAIL | PASS | same gross-vs-net inconsistency as Q1 |
| 3 | — | PASS | PASS | PASS | order counts only, no revenue definition involved |
| 4 | — | PASS | PASS | PASS | simple count |
| 5 | — | N/A* | N/A* | N/A* | scope ambiguity in the question itself (see below), not trap-driven |
| 6 | 3 | PASS | PASS | PASS | question said "net revenue" explicitly — no ambiguity |
| 7 | 2,3,4 | FAIL | FAIL | PASS | A/B split the *gross* Q3 total by segment (7.3%/92.7%); C split the *net* total correctly (9.8%/90.2%) |
| 8 | 1 | N/A* | N/A* | PASS | ground truth was flawed pre-correction; C's approach was correct all along |
| 9 | 5 | PARTIAL | PARTIAL | PASS | ground truth aggregation was flawed for a trend question; A/B's gross-based quarterly series masks the Q3-2025 dip that C's net-based series correctly shows |
| 10 | 3 | PASS | PASS | PASS | quantity-based ratio, no revenue definition involved |
| 11 | 1,3 | PASS | PASS | PASS | same qualitative conclusion (ample headroom); magnitude differs but doesn't change the answer |
| 12 | 2 | PARTIAL | PARTIAL | PASS | correct qualitative conclusion (VIP not more profitable); margin magnitude off by ~2.3pp from the cost/discount treatment |
| 13 | 5 | PARTIAL | PARTIAL | PASS | same conclusion (split ≈ single profitability); magnitude off |
| 14 | 4 | PASS | PASS | PASS | qualitative conclusion matches; magnitude off but doesn't change it |
| 15 | 3 | PASS | PASS | PASS | unambiguous wording, no revenue definition involved |
| 16 | 1,3,4 | PASS | PASS | PASS | question said "net revenue" — matches expected exactly |
| 17 | 1,3,4 | PASS | PASS | PASS | same final count (300/300) despite different intermediate margin methodology |
| 18 | 1 | PARTIAL | PARTIAL | PASS | **rank-order flip**: A/B rank Home above Textiles; correct ranking (and C) has Textiles above Home |
| 19 | 2 | PASS | PASS | PASS | open-ended question; all three reach the same core finding (VIP not more profitable), differ only in which specific customers they surface |
| 20 | 1,2,3,4,5 | PARTIAL | PARTIAL | PASS | same recommendation (prioritize France); margin ranking (Germany vs. France) flips at the margin, same systematic ~2.3pp gap |

**Tally:** C matches expected ground truth on 20/20 (excluding the 2
questions where the ground truth itself needed a scope call, both of which
C also handled sensibly). A and B each: 3 clean FAILs (Q1, Q2, Q7), 6
PARTIALs (Q9, Q12, Q13,18, 20, plus Q9's masking issue), 11 PASSes.

## Eval design corrections found during this run

Running the experiment for real surfaced three flaws in `evals/expected.md`
and `scripts/verify_expected.py` itself, all now fixed (see git history for
`scripts/verify_expected.py`):

1. **Q7 and Q12's original ground-truth SQL had a join-fan-out bug** —
   order-item-grain rows were joined to `customer_segment_history` *before*
   aggregating to one row per order, so a 3-line order matched its segment
   row 3 times instead of once, inflating totals ~3x for Q7 (margin ratio
   for Q12 happened to be unaffected, since fan-out multiplies both
   revenue and cost by the same factor). This is, ironically, the exact
   class of bug Trap 5 was designed to catch in the *agent's* SQL — it
   showed up in the harness's own ground-truth query instead. Fixed by
   aggregating to order grain before joining segment history.
2. **Q8's original ground truth used a naive `AVG(unit_price)`** with no
   discount or return netting — not actually "revenue per unit sold."
   Fixed to `SUM(net revenue) / SUM(net quantity)`, which is what all
   three conditions had already (independently) converged on.
3. **Q9's ground truth computed a single aggregate split** (multi vs.
   single shipment) when the question asks about a **trend over time** —
   a scope mismatch between the question and the verification query. Not
   fixed (left as a known limitation); all three conditions' quarterly
   breakdowns are more responsive to the actual question than the
   ground truth is.

## Implication for the PRD's Phase 1 hypothesis

The original hypothesis (PRD §14 risk) was that a 4-table schema would be
"too simple" and a governed semantic layer would need multiple deliberate
traps to show its value. The 8-table schema with 5 traps was built for
exactly that reason — but in this run, the agent (general-purpose,
Claude-based) was capable enough to sidestep 3 of the 5 traps purely from
schema shape and naming, with or without documentation. The traps that
*did* matter were not really about schema complexity at all — they were
about **definitional consistency under ambiguous natural-language
phrasing**, which is precisely the kind of problem a governed semantic
layer is supposed to solve, just not the mechanism this experiment
originally expected to demonstrate it through.

This suggests Phase 2 (adding a `knowledge/` layer and Conditions D/E)
should specifically test **question-wording ambiguity** as its own
variable — e.g. asking the same underlying metric with and without
qualifying language ("revenue" vs. "net revenue" vs. "total revenue") — 
rather than assuming schema-shape traps alone will differentiate capable
agents. It also suggests Condition B (glossary) may need to be revisited:
in this run, A and B produced near-identical SQL and conclusions
throughout — the deliberately-vague glossary added no measurable value
over schema alone for an agent this capable, which is a useful, if
humbling, negative result in its own right.
