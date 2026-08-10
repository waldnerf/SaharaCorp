# PRD: Context Layer Lab (Ossie Lab)

## 1. Executive Summary

SaharaCorp is building an internal sandbox for experimenting with AI on company data. The first concrete initiative inside that sandbox is the **Context Layer Lab** (working repo name `ossie-lab`): a controlled experimentation framework that empirically measures what an AI agent (Claude Code) needs — beyond raw database access — to reliably and correctly answer questions about a business.

The core hypothesis is that agents querying enterprise data fail or hallucinate not because they can't write SQL, but because they lack **context**: consistent definitions of business metrics, knowledge of *why* the business operates the way it does, and awareness of the processes and policies that shape the data. The lab tests this hypothesis directly by giving Claude Code the *same* set of questions against the *same* synthetic dataset, varying only the context supplied, and scoring the resulting SQL and answers against a hand-verified expected-answer set.

The semantic layer component of this context is built on the **Ossie standard**. Critically, Ossie is treated as *one layer* of a broader **context layer** — business context (goals, processes), semantic context (Ossie: entities, metrics, dimensions), knowledge context (policies, rationale), and interaction context (available actions) — rather than as the whole solution. The MVP goal is to stand up a working lab (synthetic retail company, DuckDB dataset, a graduated 20-question eval set, and 3–5 context conditions) and run it manually through Claude Code to observe, qualitatively and quantitatively, where each layer of context changes correctness. Automation of the evaluation loop into a repeatable `/run-eval` skill is an explicit next phase, not part of the MVP.

## 2. Mission

**Mission:** Determine empirically what makes an AI agent capable of understanding and reasoning about an enterprise, one layer of context at a time — starting from raw schema and building up through semantics, knowledge, and process — so that SaharaCorp can design a context architecture for agents grounded in evidence rather than assumption.

**Core principles:**
- **Evidence over intuition** — every claim about "the semantic layer helps" or "the agent needs the glossary" must be backed by a scored comparison against a fixed question set, not a vibe.
- **Business model first, data last** — the synthetic enterprise (company, processes, entities) is designed intentionally from a business model, and synthetic data is generated only after that story is coherent. Never generate tables first and invent a business around them.
- **Layers are additive and separable** — each context layer (business, semantic, knowledge, interaction) must be independently addable/removable so its marginal contribution can be isolated in an experiment.
- **Human-validated generation** — at each stage of synthetic enterprise generation (business model → capabilities → processes → use cases → semantics), a human reviews and approves before the pipeline proceeds to the next stage or to data generation.
- **Manual before automated** — run the first full eval cycle by hand through Claude Code to understand failure modes before building an automated scoring pipeline.

## 3. Target Users

**Primary persona: Internal engineer / data practitioner (e.g., the SaharaCorp team member running the lab)**
- Technical comfort level: high — comfortable with YAML, SQL, DuckDB, git, and directing Claude Code directly.
- Needs: a reproducible, low-ceremony way to test "does giving the agent X context change its answers?" without standing up real infrastructure or using sensitive company data.
- Pain points today: no standard way to compare context strategies; semantic layer tooling (dbt Semantic Layer, Cube, LookML) is heavyweight and not designed for this kind of agent-context experimentation; no synthetic enterprise dataset that's rich enough to test business reasoning, not just lookups.

**Secondary persona (future): Other SaharaCorp teams evaluating agent architectures**
- Will consume the lab's findings (which context layers matter, in what combination) to inform how they design context for production AI agents on real company data.

## 4. MVP Scope

**In Scope**

*Core Functionality*
- ✅ A synthetic retail company definition (business model, markets, objectives, value proposition) as the seed for everything downstream
- ✅ A synthetic DuckDB dataset (`data/retail.duckdb`) generated to reflect that business model, not randomly
- ✅ A glossary file (`context/glossary.md`) defining key business terms in plain language
- ✅ A semantic model expressed in the **Ossie standard** (`semantic/retail.ossie.yaml`) covering core entities, metrics, dimensions, and relationships for the retail business
- ✅ A graduated 20-question eval set (`evals/questions.md`) spanning four difficulty levels: (1) direct data lookup, (2) business "why" questions requiring analytical reasoning, (3) policy questions requiring metrics + business rules, (4) action/optimization questions requiring metrics + rules + multi-step reasoning
- ✅ A hand-verified expected-answer set (`evals/expected.md`) for scoring
- ✅ At least 3 context conditions run manually through Claude Code: (A) schema only, (B) schema + glossary, (C) schema + Ossie semantic model
- ✅ A `CLAUDE.md` describing the project and task framing for Claude Code, without revealing which condition is being tested
- ✅ Manual comparison of each condition's SQL + answers against `expected.md`, with qualitative notes on failure modes per condition

*Technical*
- ✅ Repo scaffold matching the structure below
- ✅ DuckDB as the query engine (local, file-based, no external infra)
- ✅ Ossie YAML as the semantic model format

*Out of Scope for MVP*
- ❌ Automated `/run-eval` skill (load questions → controlled context → generate SQL → execute → score → report) — planned for Phase 2
- ❌ Knowledge context layer (`knowledge/*.md` policies) and Conditions D/E (Ossie + knowledge, full context layer) — Phase 2/3
- ❌ Process context layer (business capabilities, process models, decision points) — Phase 3
- ❌ Interaction/operational context layer (actions, approvals, tool capabilities) — Phase 3+
- ❌ Business-model-first generation pipeline as a reusable, general tool (industry → business model → capabilities → processes → use cases → semantics → data) — this MVP hand-builds one instance (retail) rather than building the generator
- ❌ Human validation gates as tooling/UI — for MVP, validation is just the human reading and approving files directly
- ❌ Real company data of any kind — the lab is 100% synthetic
- ❌ Multi-company or multi-industry datasets
- ❌ Integration with BI tools, external semantic layer products (dbt, Cube), or production agent deployment
- ❌ Scoring automation, dashboards, or leaderboards across conditions

## 5. User Stories

1. **As a lab operator**, I want a synthetic retail company with a coherent business model, so that the questions I ask about it have real, defensible answers rather than arbitrary ones.
   - Example: The company sells specialty goods in France, Germany, and Belgium; "why did revenue decline in France" has an actual traceable cause in the data (e.g., a pricing or fulfillment issue in that market).

2. **As a lab operator**, I want to run the same 20 questions against Claude Code under different context conditions without telling it which condition is active, so that I get an unbiased read on what each layer contributes.
   - Example: Run condition A (schema only) in one session and condition C (schema + Ossie) in a fresh session, both given the identical instruction: "Answer the questions in evals/questions.md using the available data. For each question, provide the SQL used and the resulting answer."

3. **As a lab operator**, I want a graduated question set from simple lookups to multi-step business reasoning, so that I can see *where* (not just *whether*) additional context starts to matter.
   - Example: Level 1 "What was total revenue in France last quarter?" vs. Level 4 "Identify customers where a discount could increase revenue while keeping margin above 20%."

4. **As a lab operator**, I want an Ossie semantic model that correctly encodes metric definitions (e.g., revenue excludes returned orders), so that Condition C's advantage over Condition A is attributable to real semantic grounding, not luck.

5. **As a lab operator**, I want to compare each condition's generated SQL and final answer against a hand-verified expected answer, so that I can score correctness per question and per condition.

6. **As a lab operator**, I want to capture *why* an answer was wrong (missing definition, wrong join, wrong filter, hallucinated column) per condition, so that failure-mode patterns — not just pass/fail counts — inform what context layer addresses which failure type.

7. **As a future lab operator (Phase 2+)**, I want the eval loop automated into a `/run-eval` skill, so that adding new conditions or questions doesn't require re-running everything by hand.
   - Example: `/run-eval --condition ossie+knowledge` loads the right context, runs all 20 questions, scores against `expected.md`, and writes a report to `evals/results/`.

8. **As a future context architect (Phase 3+)**, I want the business-model-first generation pipeline (company → business model → capabilities → processes → use cases → entities → semantics → data → knowledge) with human validation gates at each stage, so that new synthetic enterprises can be generated for new experiments without hand-authoring everything from scratch.

## 6. Core Architecture & Patterns

**Conceptual architecture — the context layer sits between systems and the agent:**

```
                 AGENT (Claude Code)
                       │
                       ▼
              CONTEXT LAYER
   ┌───────────┬──────────────┬─────────────┐
   │ Business  │   Semantic   │  Knowledge  │
   │ context   │   context    │  context    │
   │ (goals,   │   (Ossie:    │  (policies, │
   │ processes)│   entities,  │  rationale) │
   │           │   metrics)   │             │
   └───────────┴──────────────┴─────────────┘
                       │
                       ▼
                 SYSTEMS (DuckDB)
```

The **semantic layer** (Ossie) answers "what does this data mean?" The **context layer** as a whole answers "what does this enterprise mean?" The MVP builds and tests only the semantic and (partially) business/glossary slices; knowledge and interaction layers are named and scoped for later phases so the architecture doesn't need to change shape as they're added.

**Repository structure:**

```
ossie-lab/
│
├── CLAUDE.md                  # Project framing for Claude Code (task instructions only —
│                               # never reveals which condition/context is active)
├── data/
│   └── retail.duckdb           # Synthetic dataset, generated from the business model
│
├── semantic/
│   └── retail.ossie.yaml       # Ossie semantic model: entities, metrics, dimensions, relations
│
├── context/
│   └── glossary.md             # Plain-language business term definitions
│
├── evals/
│   ├── questions.md            # 20 graduated questions (levels 1-4)
│   ├── expected.md             # Hand-verified expected SQL/answers
│   └── results/                # Per-condition run outputs (SQL + answer + notes)
│
└── README.md
```

**Design patterns:**
- **Condition isolation** — each condition is defined purely by which files are present/visible to Claude Code in a given session (e.g., Condition A excludes `semantic/` and `context/` entirely). No conditional logic inside prompts.
- **Business-model-first data generation** — the generation order is strictly: business model → entities/processes implied by that model → semantic model → synthetic data. Never the reverse.
- **Blind evaluation** — the task prompt given to Claude Code is identical across all conditions ("Answer the questions in evals/questions.md..."); it never names the condition or hints at what's being tested.
- **Separation of "what" from "why"** — the semantic model (Ossie) encodes metric *definitions*; the (future) knowledge layer encodes *rationale*. Keep these in separate files/formats so their individual contribution can be measured.

## 7. Tools/Features

**Feature: Synthetic retail company + dataset**
- Defines industry, markets, value proposition, objectives (in a `company:` YAML block or equivalent) as the seed artifact
- DuckDB dataset generated to be consistent with that business model (e.g., if the value prop is "fast delivery," fulfillment-time data should be plausible and support that)
- Includes at least one deliberately traceable anomaly (e.g., a France revenue decline with a real underlying cause) to support Level 2+ questions

**Feature: Ossie semantic model**
- Encodes entities (customers, orders, products), dimensions (country, product category, time), metrics (revenue, margin, retention) with precise definitions (e.g., revenue = completed orders only, excludes returns)
- Written in Ossie-standard YAML
- Must be authored so Condition C's correctness gain over Condition A/B is attributable to correct, unambiguous metric definitions

**Feature: Graduated eval question set**
- 20 questions across 4 levels:
  - Level 1 (data): direct lookups, e.g. "What was revenue in France?"
  - Level 2 (business): reasoning over trends/causes, e.g. "Why did revenue decline in France?"
  - Level 3 (policy): requires metrics + business rules, e.g. "Could we increase discounts for French customers?"
  - Level 4 (action): multi-constraint optimization, e.g. "Identify customers where a discount could increase revenue while maintaining margin above 20%"
- Each question has a hand-verified expected SQL query and answer in `expected.md`

**Feature: Manual condition runner (MVP)**
- Operator manually assembles the file set for a condition, opens a fresh Claude Code session, gives the fixed task prompt, and saves the transcript/output to `evals/results/<condition>/`
- Operator manually compares outputs to `expected.md` and records pass/fail + failure-mode notes per question

**Feature (Phase 2): `/run-eval` skill**
- Automates: load `evals/questions.md` → assemble context for a named condition → run Claude Code → capture generated SQL + answer → execute SQL against DuckDB → compare result to `expected.md` → score → write report to `evals/results/`
- Explicitly deferred until failure modes from the manual run are understood, per the "manual before automated" principle

## 8. Technology Stack

- **Agent under test:** Claude Code
- **Semantic layer format:** Ossie standard (YAML)
- **Query engine / data store:** DuckDB (local, file-based)
- **Data generation:** scripted (Python or SQL) generation from the business model definition — exact tooling TBD at implementation time
- **Repo/version control:** git (this repo)
- **Documentation/context files:** Markdown (glossary, knowledge, questions, expected answers), YAML (company/semantic definitions)
- **Phase 2 automation:** likely a Claude Code skill (`/run-eval`) invoking DuckDB via CLI or a thin Python harness — no new infra required

No external services, cloud infrastructure, or third-party semantic layer products are required for the MVP.

## 9. Security & Configuration

- **Data sensitivity:** none — all data is synthetic and fabricated for the lab. No real company or customer data is used at any phase.
- **Authentication/authorization:** not applicable — local, single-operator lab with no shared/multi-tenant access in MVP.
- **Configuration management:** all configuration is file-based (YAML/Markdown in the repo); no environment variables or secrets required for MVP since DuckDB is a local file and no external APIs are called.
- **Security scope:**
  - In scope: ensuring synthetic data never accidentally mirrors real, identifiable company data
  - Out of scope: access control, encryption, network security — irrelevant to a local single-user synthetic-data lab
- **Deployment considerations:** none — this runs entirely on the operator's local machine via Claude Code and DuckDB. No deployment target for MVP.

## 10. API Specification

Not applicable for MVP — there is no API surface. All interaction is via Claude Code sessions reading/writing local repo files and querying a local DuckDB file directly. If the Phase 2 `/run-eval` skill exposes a programmatic interface, it will be specified at that time.

## 11. Success Criteria

**MVP success is defined as:** a complete, reproducible manual run of Conditions A, B, and C against the 20-question eval set, with scored results and documented failure-mode differences between conditions.

**Functional requirements:**
- ✅ Synthetic retail company and DuckDB dataset exist and are internally consistent with the stated business model
- ✅ Ossie semantic model correctly encodes at least the metrics/entities needed to answer all 20 eval questions
- ✅ 20 questions and their expected answers are finalized and hand-verified against the actual dataset (i.e., `expected.md` answers are provably correct, not assumed)
- ✅ Conditions A, B, and C have each been run once through a fresh Claude Code session with the identical blind task prompt
- ✅ Each condition's results are scored (pass/fail per question) and compared against `expected.md`
- ✅ Failure modes are documented per condition (e.g., "Condition A hallucinated a `returns_flag` column that doesn't exist"; "Condition C correctly excluded returned orders from revenue due to the Ossie metric definition")

**Quality indicators:**
- Expected answers in `expected.md` are independently verifiable by re-running the SQL against `retail.duckdb`
- The business model is coherent enough that a human unfamiliar with the experiment could read `company:` + the dataset and find the story plausible
- At least one clear, attributable case where Condition C outperforms Condition A specifically because of a semantic definition (not because of prompt luck)

**User experience goals:**
- The operator can go from "fresh Claude Code session" to "scored answer" for one condition/question in a few minutes of manual effort
- The repo structure is self-explanatory enough that returning to the lab after a break doesn't require re-deriving what each file is for

## 12. Implementation Phases

### Phase 1 — Lab scaffold + manual A/B/C experiment (MVP)
**Goal:** Prove the experiment design works and produces a real, attributable signal about what context helps.

**Deliverables:**
- ✅ Repo scaffold (`ossie-lab/` structure as specified)
- ✅ `company:` business model definition for the synthetic retailer
- ✅ Synthetic `retail.duckdb` generated from that business model (including at least one traceable anomaly)
- ✅ `glossary.md` with plain-language term definitions
- ✅ `retail.ossie.yaml` semantic model (entities, metrics, dimensions, relationships)
- ✅ `evals/questions.md` — 20 questions across 4 difficulty levels
- ✅ `evals/expected.md` — hand-verified expected SQL + answers
- ✅ `CLAUDE.md` with a neutral, condition-blind task prompt
- ✅ Manual runs of Conditions A, B, C saved to `evals/results/`
- ✅ Scored comparison and failure-mode write-up

**Validation:** Can a third party (or the operator, a week later) read the results and understand exactly which context layer fixed which category of error?

### Phase 2 — Knowledge layer + eval automation
**Goal:** Add the "why" layer and stop doing the eval loop by hand.

**Deliverables:**
- ✅ `knowledge/*.md` policy/rationale documents (e.g., `revenue_policy.md`, `pricing_policy.md`)
- ✅ Conditions D (Ossie + knowledge) and E (full context layer as defined at this stage)
- ✅ `/run-eval` Claude Code skill: load questions → assemble condition context → run → score → report
- ✅ Re-run all conditions (A–E) via the automated pipeline for consistency with Phase 1's manual baseline

**Validation:** Automated scores for Conditions A–C match the Phase 1 manual scores (confirms the automation is faithful), and D/E show measurable improvement on Level 3–4 questions specifically.

### Phase 3 — Process context + business-model-first generator
**Goal:** Generalize from "one hand-built retail company" to a repeatable pipeline that can generate new synthetic enterprises.

**Deliverables:**
- ✅ Process context layer (capabilities, processes, decision points) for the retail company, generated *from* the business model rather than invented independently
- ✅ Formalized generation pipeline: Company/Domain → Business Model → Capabilities → Candidate Processes → Candidate Use Cases → Business Entities/Events → Semantic Model → Synthetic Data → Knowledge/Policies
- ✅ Human validation gates at each pipeline stage (business model, capabilities, processes, use cases, semantics) before proceeding
- ✅ At least one new synthetic company generated end-to-end through the pipeline as a generalization test

**Validation:** A second industry/company can be generated through the pipeline with each validation gate producing a plausible, human-approved artifact before data generation begins — confirming "business model first, data last" holds as a repeatable process, not a one-off.

### Phase 4 (future) — Interaction/operational context + agentic action
**Goal:** Extend from Q&A to agent *action* — capabilities the agent can invoke, not just query.

**Deliverables:**
- ✅ `actions/*.yaml` defining agent-invokable operations (e.g., `create_discount_request`) with required inputs and approval thresholds
- ✅ Level 4+ eval questions that require the agent to propose or simulate an action, not just answer a question
- ✅ Extended conditions testing whether interaction context changes action-proposal quality/safety

**Validation:** Deferred — scoped only after Phase 3 lands and the earlier layers' contributions are well understood.

## 13. Future Considerations

- Multi-industry synthetic enterprise library (beyond retail) to test whether findings generalize
- Comparing Ossie against alternative semantic layer formats (dbt Semantic Layer, Cube, LookML-style) on the same eval set, to understand whether results are Ossie-specific
- A leaderboard/dashboard view over `evals/results/` once enough conditions and question sets accumulate
- Applying findings from the lab to design the context architecture for a production SaharaCorp agent operating on real (non-synthetic) company data
- Extending the eval framework to other agent backends beyond Claude Code, to separate "what context helps" from "what this particular agent needs"

## 14. Risks & Mitigations

- **Risk: Synthetic business model is too simple, so all conditions score equally well and the experiment produces no signal.**
  Mitigation: deliberately design Level 3–4 questions and at least one non-obvious data anomaly (e.g., a metric definition edge case like returns handling) that *only* correct semantic/knowledge context can resolve.

- **Risk: Expected answers in `expected.md` are wrong, invalidating all scoring.**
  Mitigation: every expected answer must be produced by manually running verified SQL against `retail.duckdb` before any condition is evaluated — never hand-typed from intuition.

- **Risk: Condition leakage — Claude Code infers which condition is active from context clues (e.g., file naming, session history) and biases its answers.**
  Mitigation: use fresh sessions per condition, a single neutral task prompt in `CLAUDE.md` that never mentions conditions/experiments, and only the files relevant to that condition present in the visible repo state.

- **Risk: Manual evaluation is slow enough that only a handful of conditions ever get tested, limiting the lab's value.**
  Mitigation: explicitly scope Phase 2 to automate the loop once failure modes from the manual pass are understood — don't skip straight to automation, but don't skip it forever either.

- **Risk: Business-model-first generation (Phase 3) becomes over-engineered before it's proven necessary.**
  Mitigation: Phase 1 hand-authors one retail company without building the general pipeline; only generalize into a reusable generator in Phase 3, once there's a concrete second use case that justifies it.

## 15. Appendix

- **Semantic layer standard referenced:** Ossie
- **Query engine referenced:** DuckDB
- **Agent under test:** Claude Code
- **Key working artifact names:** `ossie-lab/` repo, `retail.duckdb`, `retail.ossie.yaml`, `glossary.md`, `questions.md`, `expected.md`
- **Terminology:**
  - *Semantic layer*: a specialized component of the context layer providing consistent representation of business meaning across data/analytics (Ossie's role here)
  - *Context layer*: the machine-readable representation of business concepts, rules, processes, knowledge, and capabilities required for an AI system to understand and act within an organization (the broader concept this lab explores)
