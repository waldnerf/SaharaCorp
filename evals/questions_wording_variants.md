# Wording-Ambiguity Variants

Phase 2c (see `.claude/plans/context-layer-lab-phase2.md`). Phase 1's
`comparison.md` found that Traps 3/4 (partial returns, multi-currency) only
actually differentiated conditions when a question's wording didn't say
"net revenue" explicitly — and that this was wording-driven, not
schema-driven, since Condition A's behavior flipped between the original
Phase 1 run (gross throughout) and the tightened-schema rerun (net
throughout) on the *identical* prompt. This file tests that finding
directly rather than assuming it.

For each of Q1, Q2, Q7 — the three questions where Condition B failed and
Condition A's answer was run-dependent — this file has 2 variants:

- **-explicit**: adds an unambiguous "net of returns" qualifier. If the
  wording hypothesis is correct, every condition (including A/B) should
  converge on the same, correct net figure here.
- **-ambiguous**: the original question, repeated verbatim, as a
  same-question control. Its only purpose is to test *reproducibility* —
  does re-running the identical ambiguous prompt against a fresh session
  reproduce the same answer twice, or does it flip again the way Condition
  A did between Phase 1's two runs?

Kept as a separate file from `evals/questions.md` (not merged) so Phase 1's
original 20-question set and its expected answers stay untouched and
independently reproducible. Same task-prompt framing as the main set: a
fresh, condition-blind session sees this file's questions with no
indication that they're variants of anything, or which original question
they pair with.

Answer format matches `evals/questions.md` / `CLAUDE.md` exactly: `## Q<id>`
heading, fenced `sql` block, `**Answer:**` line.

---

## Level 1 — Data

V1. What was total revenue (in EUR), net of any returned quantity, for each of the four markets (France, Germany, Belgium, Switzerland) over the full data period?

V2. What was total revenue (in EUR) for each of the four markets (France, Germany, Belgium, Switzerland) over the full data period?

V3. What was the average order value (net of returns) in Q1 2025, and how does it compare to the average order value (net of returns) in Q4 2024?

V4. What was the average order value in Q1 2025, and how does it compare to the average order value in Q4 2024?

## Level 2 — Business ("why")

V5. What share of France's net revenue (after netting out returned quantity) in Q3 2025 came from customers who were VIP segment at the time of purchase?

V6. What share of France's revenue in Q3 2025 came from customers who were VIP segment at the time of purchase?

---

## Pairing map (for scoring — not part of the agent-visible task)

| Variant | Pairs with | Wording |
|---|---|---|
| V1 | Q1 | explicit ("net of any returned quantity") |
| V2 | Q1 | ambiguous (verbatim repeat of Q1) |
| V3 | Q2 | explicit ("net of returns") |
| V4 | Q2 | ambiguous (verbatim repeat of Q2) |
| V5 | Q7 | explicit ("after netting out returned quantity") |
| V6 | Q7 | ambiguous (verbatim repeat of Q7) |

**Hypothesis under test:** if Phase 1's wording-ambiguity finding is
correct, V1/V3/V5 (explicit) should score PASS across every condition
including A and B, while V2/V4/V6 (ambiguous) should reproduce the same
condition-dependent split Phase 1 found on the originals — and, per the
reproducibility question this file also raises, V2/V4/V6 run under
Condition A should be checked against *both* of Phase 1's prior A results,
not just the latest one, since A's own answer already changed once between
runs on unchanged wording.
