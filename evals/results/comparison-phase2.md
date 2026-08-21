# Phase 2 Results: Conditions D/E and Wording-Ambiguity Variants

Extends [`comparison.md`](comparison.md) (Phase 1: A/B/C). Run via the MCP
question-server (`question_server/`) — a CLI wrapper
(`scripts/question_client.py`) drove each run instead of a live MCP stdio
session, since a subagent issuing separate one-shot Bash calls can't hold a
persistent JSON-RPC pipe open across calls. Each condition run was an
isolated `Agent` subagent instructed to interact *only* through that CLI
and never read another repo file — an **instruction-only** restriction, not
a hard sandbox boundary (the subagent still had technical access to the
rest of the repo). This is weaker than Phase 1's git-worktree isolation and
weaker than the MCP server's own tool-boundary isolation; treat Phase 2's
results as a good-faith replication under looser guarantees, not as strong
evidence as Phase 1's.

- **Condition D** — Ossie semantic model + `knowledge/*.md` policy docs (no glossary)
- **Condition E** — glossary + Ossie + knowledge + `context/company.yaml`
- **Wording variants** — Conditions A and B re-run against
  [`questions_wording_variants.md`](../questions_wording_variants.md) (V1-V6,
  paired with Q1/Q2/Q7)

Raw run logs: `evals/results/condition-{d,e}/run.json`,
`evals/results/wording-variants/condition-{a,b}-run.json`. Scored via
`scripts/score_run.py` and `scripts/score_variant_run.py` — automated,
not hand-transcribed.

## Headline result: a new trap, independent of the wording-ambiguity axis

**Both Condition A and Condition B wrote `(1 - oi.line_discount_pct/100.0)`
in their revenue SQL — dividing by 100 as if the column were a 0-100
percentage.** The actual data is a 0-1 fraction (max observed value 0.15,
confirmed via `SELECT MIN/MAX/AVG(line_discount_pct) FROM order_items`).
Dividing by 100 a second time shrinks the discount factor to near-zero,
overstating revenue by roughly the size of the true discount:

| Variant | A's answer (Belgium) | Canonical (Belgium) |
|---|---|---|
| V1 (explicit "net of returns") | €174,425.53 | €165,879.78 |
| V2 (ambiguous, verbatim Q1) | €179,669.98 | €165,879.78 |

Both A and B made the identical mistake, on **both** the explicit and
ambiguous wording variants — this is not the wording-ambiguity trap. It's a
new failure mode: nothing in the raw schema tells an agent that a column
named `line_discount_pct` is already a fraction rather than a whole-number
percentage, and `_pct` naming plausibly suggests the opposite. Condition
C/D/E's Ossie metric expression (`(1 - order_items.line_discount_pct)`,
`semantic/retail.ossie.yaml`) doesn't have this failure mode because it
states the exact expression rather than leaving the scale to be inferred.

**Implication:** this is now a candidate sixth trap for the dataset design,
distinct from the five shape-based traps and from Phase 1's discount-cost
trap. Unlike those, it isn't about join logic or netting — it's about a
numeric column's units/scale being invisible from the schema alone. Worth
deliberately preserving (not "fixing" the naming) in Phase 3's dataset
work, the same way Phase 1 found that removing naming tells didn't remove
the shape-based traps.

## Wording-ambiguity hypothesis: not confirmed by this data

The hypothesis (explicit "net" wording should make A/B converge on the
correct value) predicts V1/V3/V5 should PASS while V2/V4/V6 fail. That
didn't happen — V1 and V3 failed for the same reason V2/V4 did (the
discount-scale bug affects every variant identically, regardless of
wording). V5/V6 (VIP share) scored NEEDS_REVIEW rather than PASS/FAIL — the
agent's SQL returned a single aggregate row where the canonical query
returns one row per segment, a shape difference the automated scorer
correctly declines to guess about (see `scripts/score_variant_run.py`).

**Conclusion:** this run doesn't confirm or cleanly falsify Phase 1's
wording-ambiguity finding — the discount-scale bug dominates the result
and needs to be controlled for before the wording axis can be tested
cleanly. A follow-up run where A/B's SQL is first corrected for the scale
bug (or a variant question set that uses a metric unaffected by
`line_discount_pct`) would isolate the wording variable properly.

## Conditions D/E: scoring caveat

| Condition | PASS | FAIL | NEEDS_REVIEW | 
|---|---|---|---|
| D | 3 | 1 | 16 |
| E | 3 | 2 | 15 |

Most of D/E's Level 1-2 questions scored `NEEDS_REVIEW`, not because the
answers were likely wrong, but because `scripts/score_run.py` compares
result rows positionally and both agents frequently returned a different
column shape than the canonical query (e.g. an extra label column, or
`date_trunc('quarter', ...)` instead of an integer quarter number) — a
stylistic difference the scorer correctly refuses to auto-grade as
right or wrong rather than guessing. This is a known, accepted limitation
(see `.claude/plans/context-layer-lab-phase2.md`'s Edge Cases section) —
general SQL-equivalence checking is out of scope. **The raw NEEDS_REVIEW
count should not be read as "D/E performed worse than C's 20/20"** — it
means most of D/E's answers still need a human pass over
`evals/results/condition-{d,e}/run.json` before a real PASS/FAIL tally can
be trusted, the same way Phase 1's A/B/C scores came from careful human
reading, not raw row diffing.

One confirmed genuine miss in both D and E: Q3 (completed orders per
quarter) — both used `date_trunc('quarter', order_date)` giving a date
value where canonical uses an integer 1-4, which the scorer treats as a
type mismatch rather than shape mismatch since row/column counts happened
to align; this is very likely the same "different label, same underlying
grouping" issue as the shape mismatches above, not a real error, but
wasn't caught by the shape-mismatch check because DuckDB's `date_trunc`
result and canonical int result are both single-value columns. Flagged
here rather than silently counted as FAIL.

## What this run does and doesn't establish

**Does establish:** a new, real, dataset-level trap (line_discount_pct
scale) that no prior phase surfaced, independently reproduced by two
conditions on two different questions.

**Does not establish:** a clean D vs. E comparison, or confirmation of the
wording-ambiguity hypothesis — both require either fixing
`scripts/score_run.py`'s shape-comparison limitation or a human scoring
pass, and a wording-variant re-run that isolates the scale bug.

## Next steps

1. Human review of the 31 combined NEEDS_REVIEW rows across D/E
   (`evals/results/condition-{d,e}/run.json` + `score.md`) to get a real
   PASS/FAIL tally comparable to Phase 1's.
2. Re-run the wording variants with the discount-scale bug controlled for,
   to actually test the wording-ambiguity hypothesis in isolation.
3. Consider adding `line_discount_pct` scale as an explicit sixth
   trap-coverage entry in `evals/questions.md` if Phase 3 keeps it.
4. Re-run Conditions D/E and the wording variants with true process-level
   isolation (headless `claude -p` per the `/run-eval` skill's preferred
   path) once available, to get isolation guarantees back up to Phase 1's
   level — this run's instruction-only isolation is a real, documented
   weakening, not equivalent to Phase 1's worktree-based process.
