# Expected Answers — Wording-Ambiguity Variants

Ground truth for `evals/questions_wording_variants.md`, derived by running
`python -m scripts.verify_expected_wording_variants` against
`data/retail.duckdb`. Every value below is transcribed verbatim from that
script's output — none hand-typed or estimated.

Each variant's canonical answer is **identical** to its paired original
question (Q1/Q2/Q7) — see `evals/expected.md`. That's the point: wording
never changes what's correct, only what the ambiguous phrasing lets an
under-contexted agent get away with computing instead.

---

## V1 — Total revenue by market, explicit "net" (pairs with Q1)

**Answer:** Belgium €165,879.78 · France €290,224.44 · Germany €258,889.36 · Switzerland €158,781.01

## V2 — Total revenue by market, ambiguous control (pairs with Q1)

**Answer:** Belgium €165,879.78 · France €290,224.44 · Germany €258,889.36 · Switzerland €158,781.01 (identical to V1 and to Q1 — same governed computation regardless of wording)

## V3 — AOV Q1-2025 vs Q4-2024, explicit "net" (pairs with Q2)

**Answer:** Q4-2024: €453.91 (340 orders) · Q1-2025: €472.35 (290 orders) — AOV rose ~4%.

## V4 — AOV Q1-2025 vs Q4-2024, ambiguous control (pairs with Q2)

**Answer:** Q4-2024: €453.91 (340 orders) · Q1-2025: €472.35 (290 orders) — AOV rose ~4% (identical to V3 and to Q2).

## V5 — VIP share of France Q3-2025 revenue, explicit "net" (pairs with Q7)

**Answer:** VIP: €2,941.76 (9.81%) · standard: €27,056.06 (90.19%)

## V6 — VIP share of France Q3-2025 revenue, ambiguous control (pairs with Q7)

**Answer:** VIP: €2,941.76 (9.81%) · standard: €27,056.06 (90.19%) (identical to V5 and to Q7).

---

## Scoring note

Because every variant's correct numeric answer is identical to its parent
question's, `scripts/score_run.py` can score these directly by reusing the
parent question's canonical SQL from `scripts.verify_expected.QUERIES` — no
separate ground-truth table is needed at scoring time, only the pairing map
in `evals/questions_wording_variants.md`'s "Pairing map" section. What
varies across a real condition run is not the expected *value* but whether
each condition's agent-written SQL nets returns correctly for the
ambiguous-wording variants (V2/V4/V6) the same way it does for the
explicit-wording ones (V1/V3/V5) — that divergence, not a wrong number
against these values, is the actual signal Phase 2c is testing for.
