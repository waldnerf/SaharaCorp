# Feature: Context Layer Lab — Phase 2 (Knowledge Layer + Eval Automation)

The following plan should be complete, but it's important that you validate documentation and codebase patterns and task sanity before you start implementing.

This is **not** a greenfield phase — Phase 1 (commits `28d64fc`, `f65ca08`) already built the full retail dataset, Ossie semantic model, glossary, 20-question eval set, and a manual A/B/C comparison. Read [`evals/results/comparison.md`](../../evals/results/comparison.md) in full before starting anything else — it is the empirical evidence this plan is designed around, not a hypothesis. Two of its findings directly reshape Phase 2 relative to how the PRD originally scoped it (see "How Phase 1's findings change this plan" under NOTES).

## Feature Description

Add the "why" layer (`knowledge/*.md`) on top of the existing semantic layer, introduce Conditions D (Ossie + knowledge) and E (glossary + Ossie + knowledge), add a **question-wording-ambiguity axis** to the eval set to directly test Phase 1's headline finding, and build a `/run-eval` skill that automates the condition-run → score → report loop that was done by hand in Phase 1f.

## User Story

As a lab operator (SaharaCorp data/engineering team)
I want the knowledge/rationale layer added to the context stack, a repeatable automated eval runner, and a targeted test of the wording-ambiguity failure mode Phase 1 surfaced
So that I can measure whether "why" context improves policy/action-level reasoning specifically, and stop re-deriving Phase 1's manual process by hand for every new condition or question

## Problem Statement

Phase 1 proved the lab design works but surfaced two things the original Phase 2 scope (as written in [PRD.md](../../PRD.md) §12) doesn't yet account for:

1. The traps that actually differentiated conditions (Traps 3 & 4, expressed as "gross vs. net revenue") were triggered by **ambiguous question wording**, not by schema shape — 3 of 5 designed traps were avoided by Condition A on schema alone. Phase 2 as originally scoped (knowledge layer + D/E + automation) does not test wording ambiguity as its own variable, so it would build two new conditions on top of an untested assumption.
2. Condition B (glossary) produced answers nearly identical to Condition A throughout Phase 1 — the glossary added no measurable value for an agent this capable. Continuing to run B unchanged in every future phase without re-testing that finding wastes eval cycles on a condition that may not be pulling weight.

Also, hand-running three Claude Code sessions and eyeballing 20×N answers against `expected.md` does not scale past 3 conditions — Phase 2 adds 2 more (D, E), making manual scoring for 5 conditions × 20 questions = 100 comparisons impractical to keep doing by hand for every eval-set change going forward.

## Solution Statement

Build the knowledge layer as markdown "why" documents mapped 1:1 to the specific definitional decisions Phase 1 found were either ungoverned (the discount-vs-cost treatment that caused Q18's rank flip) or under-motivated (why returns net at line grain, why segment is point-in-time). Add Conditions D and E per the PRD. Separately — and this is the part Phase 1's evidence adds beyond the PRD's original Phase 2 scope — extend `evals/questions.md` with a small set of **wording-paired variants** of already-answered questions (same metric, different qualifying language), scored as their own axis so the wording-ambiguity finding can be confirmed or falsified with new data rather than assumed. Build `/run-eval` as a Claude Code skill that orchestrates isolated per-condition runs (via git worktrees, mirroring Phase 1f's manual process) and auto-scores the objective (SQL-derived numeric) questions by re-executing agent SQL against DuckDB and diffing against canonical values already computed in `scripts/verify_expected.py`; qualitative Level 3/4 questions remain flagged for human (or later, LLM-judge) review rather than force-automating a fuzzy comparison.

## Feature Metadata

**Feature Type**: Enhancement (extends Phase 1's lab with a new context layer, new conditions, and automation)
**Estimated Complexity**: Medium-High — the knowledge docs and new eval questions are low-risk content work; `/run-eval`'s automated SQL-diff scoring is the one genuinely new technical mechanism and has real design risk (see Risks in NOTES)
**Primary Systems Affected**: `knowledge/` (new), `evals/questions.md` (extended), `.claude/skills/run-eval/` (new skill), `evals/results/` (new condition outputs + a Phase 2 comparison), `scripts/verify_expected.py` (reused, not rewritten)
**Dependencies**: Same as Phase 1 (`duckdb`, `pyyaml`, `pytest`) — no new external dependencies. `/run-eval` reuses the git-worktree isolation pattern and the `Agent` tool (or headless `claude` CLI invocation) to run fresh, blind sessions per condition.

---

## CONTEXT REFERENCES

### Relevant Codebase Files — read before implementing

- [`evals/results/comparison.md`](../../evals/results/comparison.md) — the Phase 1 findings this plan is built on. Read in full, especially "Headline result," the scored table, and "Implication for the PRD's Phase 1 hypothesis."
- [`evals/expected.md`](../../evals/expected.md) — canonical answers Phase 2's automated scorer must diff against. Note the two "Correction:" notes (Q7/Q8/Q12) — these are the ground truth as of Phase 1, already bug-fixed once.
- [`scripts/verify_expected.py`](../../scripts/verify_expected.py) — one hardcoded SQL query per question, `NET_REVENUE`/`NET_COST` shared expression constants. `/run-eval`'s scorer reuses this file's canonical query results rather than re-deriving them — do not duplicate this logic.
- [`semantic/retail.ossie.yaml`](../../semantic/retail.ossie.yaml) (lines 371-445 for `metrics:`) — `net_cost` already applies `(1 - line_discount_pct)`, i.e. Condition C already resolves the discount-vs-cost ambiguity structurally. This is why the knowledge layer's contribution there is explanatory ("why"), not corrective — Condition C's *numbers* don't change with the knowledge layer; only D/E's ability to *justify* a policy-level recommendation should improve.
- [`context/glossary.md`](../../context/glossary.md) — Condition B's file; deliberately vague, unchanged by this plan except for the reassessment task below.
- [`context/company.yaml`](../../context/company.yaml) — business model seed; `priorities.reduce_return_rate_in_underperforming_markets` is the anchor the `knowledge/revenue_recognition_policy.md` doc should trace back to, per Phase 1's forward-compatibility note.
- [`CLAUDE.md`](../../CLAUDE.md) (repo root) — the neutral task prompt. Stays **byte-identical** across all 5 conditions in Phase 2, same as Phase 1's A/B/C.
- `.claude/plans/context-layer-lab-phase1.md` — Phase 1's plan. Mirror its structure, its condition-isolation pattern (git worktrees), and its "library not skill" reasoning where applicable — `/run-eval` is the one place Phase 1 explicitly deferred skill-building to Phase 2, so this is where that deferred decision gets executed.
- [PRD.md](../../PRD.md) §12 Phase 2 (lines 233-242) — the original scope this plan implements, amended per "How Phase 1's findings change this plan" below.

### New Files to Create

- `knowledge/revenue_recognition_policy.md` — why returns net at line grain regardless of order status, tied to `company.yaml`'s return-rate priority
- `knowledge/pricing_snapshot_policy.md` — why historical revenue/margin must use transaction-time price (`order_items.unit_price`), never current `product_price_history`, for financial reporting integrity
- `knowledge/discount_cost_policy.md` — why a line discount reduces recognized cost proportionally as well as revenue (the exact ambiguity that caused Q18's category rank-flip in Phase 1) — this is the single highest-value new knowledge doc, since it's the one real gap Phase 1 found was undocumented anywhere
- `knowledge/segment_attribution_policy.md` — why customer segment must be evaluated point-in-time (at order date) for revenue-attribution questions, not current segment
- `evals/questions_wording_variants.md` — 6-8 new questions, each a **wording-paired variant** of an existing Phase 1 question, isolating the "revenue" vs. "net revenue" vs. "total revenue" ambiguity as its own scored axis (see Phase 2c below) — kept as a separate file (not merged into `evals/questions.md`) so Phase 1's 20-question set and its expected answers stay untouched and independently reproducible
- `evals/expected_wording_variants.md` — hand-verified expected answers for the new variant questions, produced the same way as Phase 1 (`scripts/verify_expected.py`, extended)
- `.claude/skills/run-eval/SKILL.md` — the new automation skill (see Phase 2e)
- `scripts/score_transcript.py` — reusable scorer: given a condition's transcript, extracts each question's SQL, re-executes it against `data/retail.duckdb`, and diffs the numeric result against the canonical value (imported from `scripts/verify_expected.py`'s `QUERIES`/expected outputs) within a tolerance; flags non-numeric/qualitative questions (Level 3/4) as `NEEDS_REVIEW` rather than guessing
- `evals/results/condition-d/`, `evals/results/condition-e/` — new transcripts, same shape as A/B/C
- `evals/results/comparison-phase2.md` — the Phase 2 findings write-up, extending (not replacing) `comparison.md`

### Relevant Documentation — read before implementing

- Phase 1 already established the Ossie syntax reference and DuckDB/Faker gotchas — nothing new to research there; the knowledge docs are plain markdown with no external format dependency (PRD §7 "Separation of 'what' from 'why'" — keep `knowledge/` as prose, not YAML, to keep the semantic-vs-knowledge distinction structurally visible, not just conventional)
- No new libraries are needed for `/run-eval`; it orchestrates existing tools (`git worktree`, the `Agent` tool or `claude -p` headless invocation, `duckdb`) rather than introducing new ones

### Patterns to Follow

**Condition isolation (unchanged from Phase 1):** each condition is defined purely by which files are visible in the worktree, `CLAUDE.md` never changes, no condition name ever appears in the task prompt.

**Condition file matrix for Phase 2:**

| Condition | `context/glossary.md` | `semantic/retail.ossie.yaml` | `knowledge/*.md` |
|---|---|---|---|
| A (baseline, re-run only if wording variants are added) | – | – | – |
| B | ✅ | – | – |
| C | – | ✅ | – |
| D | – | ✅ | ✅ |
| E | ✅ | ✅ | ✅ |

**Knowledge doc pattern:** each file states the policy, then a **Why** section grounding it in a specific business consequence (ideally traceable to `company.yaml`'s `priorities`/`kpis`), then explicitly notes which trap/ambiguity it resolves — mirroring the "Why" structure already used in this session's own memory files, for consistency of reasoning style across the project. Keep each doc under ~150 words; the knowledge layer's job is rationale, not restating the Ossie metric's SQL.

**Automated scoring pattern:** `scripts/score_transcript.py` must import `QUERIES`/results from `scripts/verify_expected.py` rather than re-hardcoding expected values a second time — Phase 1 already demonstrated that hand-duplicated ground truth drifts and produces bugs (the Q7/Q8/Q12 fan-out and naive-metric bugs). One canonical source of expected values, reused everywhere.

---

## IMPLEMENTATION PLAN

### Phase 2a: Knowledge layer

**Tasks:**
- Write the four `knowledge/*.md` docs listed above
- Cross-check each doc resolves something Phase 1 found ungoverned or under-motivated — do not invent new policies unconnected to an actual Phase 1 finding

### Phase 2b: Conditions D and E

**Tasks:**
- Run Condition D (Ossie + knowledge) and Condition E (glossary + Ossie + knowledge) as fresh, isolated sessions per the git-worktree pattern from Phase 1f
- Save transcripts to `evals/results/condition-d/`, `evals/results/condition-e/`

### Phase 2c: Wording-ambiguity axis (new — not in the original PRD Phase 2 scope, added because of Phase 1's finding)

**Tasks:**
- Write `evals/questions_wording_variants.md`: for each of Q1, Q2, Q7 (the three Phase 1 clean FAILs, all driven by gross-vs-net ambiguity), write 2 additional wording variants of the same underlying question — one with an explicit qualifier ("net revenue," "total revenue including returns") and one left as ambiguous as the original. This isolates whether the failure is really about wording (as comparison.md concluded) or about something else that happened to correlate with those three questions.
- Extend `scripts/verify_expected.py` (or a small sibling script) to compute canonical answers for the variants; write `evals/expected_wording_variants.md`
- Re-run Conditions A and B specifically against the variant set (C/D/E are expected, per Phase 1's analysis, to be wording-invariant since they use a named governed metric regardless of question phrasing — confirm this rather than assume it, but it is not the primary hypothesis under test here)

### Phase 2d: Condition B reassessment

**Tasks:**
- After Phase 2c's results are in, explicitly answer: did B (glossary) diverge from A (schema-only) on **any** question in Phase 1, the new D/E conditions, or the wording variants? If B has now had two full eval passes (Phase 1 + Phase 2) with zero attributable wins over A, record that finding plainly in `comparison-phase2.md` and recommend dropping B from Phase 3's condition matrix (replacing it with a business-context condition per PRD's Conditions naming, or retiring it) rather than continuing to run a condition with no demonstrated signal.

### Phase 2e: `/run-eval` skill

**Tasks:**
- Build `.claude/skills/run-eval/SKILL.md` implementing: given `--condition <name>`, resolve which files that condition includes (from the matrix above, stored as a small config — e.g. `evals/conditions.yaml` mapping condition name → list of paths to include), create/reuse a git worktree with exactly those files, invoke a fresh agent against `CLAUDE.md`'s task (via the `Agent` tool with a plain subagent, or `claude -p` headless if run outside a Claude Code session — pick one and document why in the skill), capture the transcript, run `scripts/score_transcript.py` against it, and write both the transcript and a per-condition score summary to `evals/results/<condition>/`
- `evals/conditions.yaml` (new, small): declarative condition→files mapping, so adding Condition F later is a config change, not a code change

---

## STEP-BY-STEP TASKS

Execute in order, top to bottom.

### CREATE `knowledge/discount_cost_policy.md`

- **IMPLEMENT**: policy — "when a line item is sold at a discount, the cost of goods sold recognized for that line is reduced by the same discount percentage as the revenue, so margin percentage is invariant to discount depth." Why — ties to `company.yaml`'s `priorities` (protecting margin while allowing discount flexibility, see Q11/Q17 in Phase 1). Explicitly note this is what `semantic/retail.ossie.yaml`'s `net_cost` metric already encodes (`(1 - line_discount_pct)` applied to cost, not just revenue) and that Conditions A/B had no access to this rationale, which is why they made a different, undocumented assumption in Phase 1 (Q12, Q13, Q18, Q20 PARTIALs)
- **VALIDATE**: manual read-through — confirm the doc's stated rule matches `semantic/retail.ossie.yaml` lines 395-410 exactly (no invented policy that contradicts the actual metric)

### CREATE `knowledge/revenue_recognition_policy.md`

- **IMPLEMENT**: policy — returns net against revenue at the line-item grain regardless of order status, because order status only tracks fulfillment/cancellation, not post-sale returns. Why — trace to `company.yaml`'s `reduce_return_rate_in_underperforming_markets` priority and the France Q3 anomaly (Q6/Q15 in Phase 1)
- **VALIDATE**: same pattern — confirm consistency with `semantic/retail.ossie.yaml`'s `revenue` metric

### CREATE `knowledge/pricing_snapshot_policy.md`

- **IMPLEMENT**: policy — historical revenue/margin always uses the price actually charged at transaction time (`order_items.unit_price`), never a product's current price, because re-stating historical periods at today's prices would misrepresent past performance
- **VALIDATE**: same pattern

### CREATE `knowledge/segment_attribution_policy.md`

- **IMPLEMENT**: policy — a customer's segment for any historical revenue-attribution question is their segment **as of the order date**, not their current segment, because attributing past revenue to a customer's current (possibly later-earned) VIP status would overstate VIP's historical contribution
- **VALIDATE**: same pattern

### CREATE `evals/questions_wording_variants.md`

- **IMPLEMENT**: 6 questions — 2 wording variants each for Q1 (revenue by market), Q2 (AOV), Q7 (VIP revenue share): one variant uses an explicit qualifier ("net revenue," "revenue after returns"), one repeats the original ambiguous phrasing verbatim (as a same-question control to confirm reproducibility of the original Phase 1 result). Tag each with which original question it pairs with.
- **VALIDATE**: manual count — exactly 6 questions, each traceable to Q1/Q2/Q7

### EXTEND `scripts/verify_expected.py` (or CREATE sibling script for variants)

- **IMPLEMENT**: canonical SQL + results for the 6 variant questions, reusing the existing `NET_REVENUE`/`NET_COST` constants
- **VALIDATE**: `python -m scripts.verify_expected` (or the sibling script) runs clean; transcribe into `evals/expected_wording_variants.md`

### RUN Condition A and B against wording variants

- **IMPLEMENT**: fresh worktree sessions (Condition A's and B's existing file sets), task = answer the 6 variant questions (append to `evals/questions.md` temporarily for that session, or point at `evals/questions_wording_variants.md` directly with an equally neutral prompt); save transcripts to `evals/results/condition-a/wording-variants.md`, `evals/results/condition-b/wording-variants.md`
- **VALIDATE**: transcripts contain 6 answered questions each with SQL

### CREATE `evals/conditions.yaml`

- **IMPLEMENT**: `{condition_name: [list of repo-relative paths to include, always includes data/ and evals/questions.md and CLAUDE.md]}` for A-E
- **VALIDATE**: `python -c "import yaml; d=yaml.safe_load(open('evals/conditions.yaml')); assert set(d) >= {'a','b','c','d','e'}"`

### CREATE `scripts/score_transcript.py`

- **IMPLEMENT**: `score_transcript(transcript_path, question_ids=None) -> list[ScoreResult]` — parses fenced SQL blocks per question from a transcript (match the heading format already used in Phase 1's condition transcripts), executes each against `data/retail.duckdb` read-only, compares the numeric result to the canonical value pulled from `scripts.verify_expected.QUERIES`/output within a relative tolerance (e.g. 0.5%) for float comparisons; questions whose expected answer in `expected.md` is prose/qualitative (Level 3/4) are marked `NEEDS_REVIEW`, not force-scored
- **GOTCHA**: reuse `scripts.verify_expected`'s query text as the source of canonical values — do not hand-copy numbers into this script (this is exactly the mistake that caused Phase 1's Q7/Q8/Q12 ground-truth bugs, just in a different file)
- **VALIDATE**: run against one of Phase 1's existing transcripts (e.g. `evals/results/condition-c/transcript.md`) and confirm it reproduces `comparison.md`'s Condition C scores (20/20 PASS on the objective questions) — this is the automation's own correctness check, analogous to PRD §12 Phase 2's validation ("automated scores for A-C match Phase 1's manual scores")

### CREATE `.claude/skills/run-eval/SKILL.md`

- **IMPLEMENT**: a skill invocable as `/run-eval --condition <name>` that: reads `evals/conditions.yaml` for the file set, creates/reuses a git worktree with that file set (mirroring Phase 1f's `git worktree add` + `rm -rf` pattern), spawns a fresh isolated agent (via the `Agent` tool, `general-purpose` subagent, given only the worktree path and the neutral task instruction — no knowledge of the experiment) against that worktree, saves the returned transcript to `evals/results/<condition>/transcript.md`, runs `scripts/score_transcript.py` against it, and appends a scored summary to `evals/results/<condition>/score.md`
- **PATTERN**: mirror Phase 1f's manual process exactly — the skill should be "the same steps a human operator did, invoked as one command," not a redesign
- **GOTCHA**: the spawned agent must not have access to this conversation's context (no shared memory of the experiment, condition names, or expected answers) — use a fresh `Agent` call, never `SendMessage` to a continuing agent
- **VALIDATE**: `/run-eval --condition c` reproduces (within scoring tolerance) Condition C's Phase 1 result

### CREATE `evals/results/comparison-phase2.md`

- **IMPLEMENT**: extends `comparison.md` — scores D/E against expected.md, confirms or falsifies the wording-ambiguity hypothesis using the Phase 2c results (does C/D/E stay wording-invariant while A/B do not, or does even C waver on some phrasing?), states the Condition B keep/drop recommendation from Phase 2d, and validates `/run-eval`'s automated scores against Phase 1's manual scores for A-C per PRD §12's Phase 2 validation criterion
- **VALIDATE**: manual review against PRD §12 Phase 2's stated validation: "Automated scores for Conditions A–C match the Phase 1 manual scores... and D/E show measurable improvement on Level 3–4 questions specifically"

---

## TESTING STRATEGY

### Unit Tests

`scripts/score_transcript.py` needs its own small test (`tests/test_score_transcript.py`): feed it a synthetic transcript with a known-correct and a known-wrong SQL answer for a couple of Phase 1 questions, assert PASS/FAIL classification is correct, and assert a Level 3/4 question is classified `NEEDS_REVIEW` not force-scored.

### Integration Tests

Running `/run-eval --condition c` end-to-end and diffing its output against Phase 1's manual Condition C result **is** the integration test for the whole automation mechanism (see PRD §12 Phase 2's own validation criterion) — do not consider `/run-eval` done until this specific reproduction check passes.

### Edge Cases

- A question where the agent's SQL is syntactically valid but semantically different from the canonical query yet coincidentally produces the same number (false PASS risk) — acceptable, known limitation; note it in `comparison-phase2.md` rather than trying to solve general SQL-equivalence checking
- A question where the agent's answer is well-reasoned but the SQL block extraction regex misses it (e.g. non-fenced SQL, multiple candidate queries per question) — `score_transcript.py` should mark these `PARSE_ERROR` and surface them for manual check rather than silently mis-scoring
- Wording variants must actually differ meaningfully in ambiguity, not just cosmetically — sanity check by having a human (not an LLM) confirm the "ambiguous" variant genuinely lacks the qualifying language before running conditions against it

### E2E / Browser Automation

Not applicable — no UI, same as Phase 1.

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style

```bash
ruff check scripts/ tests/
python -c "import yaml; yaml.safe_load(open('evals/conditions.yaml'))"
```

### Level 2: Unit Tests

```bash
pytest tests/test_score_transcript.py -v
```

### Level 3: Integration Tests

```bash
python -m scripts.verify_expected   # unchanged, must still pass after Phase 1
python scripts/score_transcript.py evals/results/condition-c/transcript.md   # regression check against Phase 1's own transcript
```

### Level 4: Manual Validation

- Confirm each `knowledge/*.md` doc's stated policy matches the corresponding `semantic/retail.ossie.yaml` expression exactly (no drift between "what" and "why")
- Confirm `evals/questions_wording_variants.md` variants are traceable to Q1/Q2/Q7 and genuinely differ in qualifying language
- Confirm `CLAUDE.md` is unchanged and still contains no condition-identifying language

### Level 5: Condition Runs (manual or via `/run-eval` once built)

```bash
/run-eval --condition d
/run-eval --condition e
/run-eval --condition a --questions evals/questions_wording_variants.md
/run-eval --condition b --questions evals/questions_wording_variants.md
```

### Level 6: Additional Validation

None required.

---

## ACCEPTANCE CRITERIA

- [ ] Four `knowledge/*.md` docs exist, each traceable to a specific Phase 1 finding and consistent with the corresponding Ossie metric
- [ ] Conditions D and E have been run and scored against `evals/expected.md`
- [ ] `evals/questions_wording_variants.md` + `evals/expected_wording_variants.md` exist, and Conditions A and B have been re-run against them
- [ ] `comparison-phase2.md` explicitly confirms or falsifies the wording-ambiguity hypothesis with new data, not by re-asserting Phase 1's conclusion
- [ ] `comparison-phase2.md` makes an explicit, evidence-based keep/drop recommendation for Condition B
- [ ] `/run-eval --condition c` reproduces Phase 1's manual Condition C scores within `score_transcript.py`'s tolerance
- [ ] `scripts/score_transcript.py` imports canonical values from `scripts/verify_expected.py` rather than duplicating them
- [ ] No regressions: Phase 1's existing tests (`pytest tests/`) and `scripts/verify_expected.py` still pass unchanged

## COMPLETION CHECKLIST

- [ ] All tasks completed in order (2a → 2e)
- [ ] `ruff check` and YAML parse checks pass with zero errors
- [ ] `pytest tests/` (including new `test_score_transcript.py`) passes fully
- [ ] `/run-eval --condition c` reproduction check passes
- [ ] `evals/results/comparison-phase2.md` written and reviewed against PRD §12 Phase 2's validation criterion
- [ ] Acceptance criteria above all met

---

## NOTES

**How Phase 1's findings change this plan, relative to the PRD's original Phase 2 scope:**

1. The PRD's Phase 2 (§12) as written only adds knowledge + D/E + automation. It does not test question-wording ambiguity as its own variable, even though Phase 1's own evidence (comparison.md) says that's the mechanism that actually differentiated conditions, not schema-shape traps. Phase 2c is new relative to the PRD, added specifically because of this evidence — skipping it would mean building D/E on top of an untested assumption about *why* C outperformed A/B.
2. The PRD assumes Condition B continues unchanged indefinitely. Phase 1 found zero attributable B-over-A wins across 20 questions. Phase 2d gives B one more real chance (the wording variants) before recommending a keep/drop decision, rather than silently continuing to run a condition that may not be earning its place in the matrix.

**Why `/run-eval`'s scorer only automates objective (numeric) questions:** Level 3/4 questions in this eval set are open-ended ("could discounts increase without margin dropping below 20%") with prose answers, not single numbers. Force-automating a fuzzy text comparison against `expected.md`'s prose would either be too strict (penalizing valid alternate phrasing) or too loose (passing wrong reasoning that happens to mention the right keywords). Flagging these `NEEDS_REVIEW` and keeping a human (or, later, an LLM-judge pass — explicitly out of scope for this plan) in the loop for qualitative scoring is the honest choice, not a shortcut.

**Why the spawned agent for `/run-eval` should be the `Agent` tool, not a new `claude -p` subprocess, if built inside a Claude Code session:** Phase 1's manual runs already validated that a fresh `Agent` tool call with no shared context is an adequate proxy for "a fresh Claude Code session" (this was the exact mechanism used for A/B/C). Reusing that same primitive keeps `/run-eval`'s results comparable to Phase 1's, which matters for the reproduction validation in Level 5. If `/run-eval` needs to run outside any Claude Code session (e.g. from CI), documenting a `claude -p` headless fallback is reasonable but is not the primary path this plan builds.

**Confidence score: 6/10.** The knowledge docs and wording-variant questions are low-risk content work (similar to Phase 1c/1d, which went smoothly). The real uncertainty is `/run-eval`'s SQL-extraction-and-diff scorer — transcript formats can vary agent-to-agent even with a neutral prompt (Phase 1's three transcripts were not byte-identical in structure), so `score_transcript.py`'s parsing step should be expected to need iteration, and the plan explicitly budgets a `PARSE_ERROR` fallback rather than assuming clean extraction on the first pass. Lower than Phase 1's 7/10 because this phase adds a genuinely new automation mechanism rather than replicating an already-proven manual process.
