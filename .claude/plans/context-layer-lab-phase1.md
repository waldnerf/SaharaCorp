# Feature: Context Layer Lab — Phase 1 (Scaffold + Manual A/B/C Experiment)

The following plan should be complete, but it's important that you validate documentation and codebase patterns and task sanity before you start implementing.

This is a **greenfield repo** — there is no existing application code, so there are no internal patterns to mirror. The conventions below (Python layout, DuckDB usage, Ossie YAML syntax) are being established by this plan, not extracted from prior code. Pay special attention to getting the retail schema, the Ossie YAML syntax, and the metric definitions exactly as specified — these are the load-bearing artifacts of the whole experiment.

**Schema complexity is deliberate and load-bearing.** A flat 4-table schema (customers/products/orders/order_items) with one price, one currency, and order-level status is too simple to isolate what a semantic layer actually buys you — a schema-only agent can get it right by luck. This plan instead builds in five classic, well-documented dimensional-modeling traps (snapshot-vs-current pricing, a slowly-changing dimension, line-grain partial returns decoupled from order status, multi-currency conversion, and a fan-out join via split shipments) so that Condition A (schema only) has concrete, predictable ways to fail, and Condition C (schema + Ossie) has concrete, predictable ways to succeed *because of specific metric/join definitions*, not chance. See the "Deliberate semantic traps" list under Patterns to Follow, and NOTES at the end, for the full rationale.

## Feature Description

Build the `ossie-lab` sandbox: a synthetic retail company + DuckDB dataset, a glossary, an Ossie-standard semantic model, a 20-question graduated eval set with hand-verified expected answers, and a neutral `CLAUDE.md` task prompt — then manually run Claude Code against three context conditions (schema only / schema+glossary / schema+Ossie) and document which context layer fixes which class of error. This is Phase 1 of the Context Layer Lab described in [PRD.md](../../PRD.md).

## User Story

As a lab operator (SaharaCorp data/engineering team)
I want a reproducible synthetic retail dataset and a graduated question set that I can run through Claude Code under different context conditions
So that I can empirically observe which layers of context (raw schema, glossary, Ossie semantic model) change agent correctness, and where

## Problem Statement

There is currently no repo, dataset, or eval set to run this experiment — everything must be built from scratch. Without a coherent business model behind the data, questions like "why did revenue decline in France" have no real answer, and any experiment result would be unfalsifiable.

## Solution Statement

Design one coherent synthetic retail company (business model → schema → data, in that order, per [PRD.md](../../PRD.md) §6), generate its DuckDB dataset with a Python script (reproducible via a fixed random seed), hand-author the Ossie semantic model and glossary against that exact schema, write 20 questions whose expected answers are derived by actually querying the generated database (never invented from intuition), then manually run three Claude Code sessions — one per condition — and record results.

## Feature Metadata

**Feature Type**: New Capability (greenfield)
**Estimated Complexity**: Medium — no technical difficulty per component, but many interdependent artifacts (business model → schema → data → semantic model → questions → expected answers) must stay mutually consistent
**Primary Systems Affected**: New repo structure at project root; Python data-generation script; DuckDB file; YAML/Markdown context files; Claude Code sessions (manual, not automated in this phase)
**Dependencies**: Python 3.11+, `duckdb` (Python package), `faker` (synthetic data), `pytest` (sanity checks on generated data). No external services.

---

## CONTEXT REFERENCES

### Relevant Codebase Files — read before implementing

- [PRD.md](../../PRD.md) — the full product spec this plan implements. Read §4 (MVP Scope), §6 (Architecture — repo structure), §7 (Tools/Features), §11 (Success Criteria), and §12 Phase 1 (Deliverables + Validation) in full before starting. This plan is a direct execution of PRD §12 Phase 1.
- `README.md` (project root) — one-line project description ("SaharaCorp, a big sandbox for AI on company data"); confirms this lab lives at the repo root, not in a subdirectory.
- Repo root currently contains only `LICENSE`, `README.md`, `PRD.md`, `.claude/` — there is no existing `src/`, `app/`, or build tooling to integrate with. Do not assume any existing package manager config; this plan creates it.

### New Files to Create

- `pyproject.toml` — Python project config: dependencies (`duckdb`, `faker`, `pytest`, `ruff`), Python `>=3.11`
- `scripts/lib/synthetic_traps.py` — **domain-agnostic** reusable library implementing the 5 trap mechanisms (SCD Type 2 history, point-in-time snapshot lookup, child-grain reversal, FX-rate generation, auxiliary fan-out fact) as parameterized functions with no retail-specific table/column names baked in — this is the reusable unit a future domain (or a future Phase 3 generation skill) calls into
- `scripts/generate_data.py` — the retail-specific **recipe**: defines retail's tables/columns and calls into `scripts/lib/synthetic_traps.py` for each trap; generates `data/retail.duckdb` from the business model, with a fixed seed for reproducibility
- `scripts/verify_expected.py` — runs each SQL query from `evals/expected.md` against `data/retail.duckdb` and prints results, so expected answers are always derived from real query execution, not typed by hand
- `tests/test_synthetic_traps.py` — pytest unit tests for the library **in isolation**, using a throwaway toy domain (not retail) to prove the functions are actually domain-agnostic and not accidentally coupled to retail's shape
- `tests/test_generated_data.py` — pytest sanity checks on the generated retail dataset (row counts, referential integrity, presence of the deliberate anomaly)
- `context/company.yaml` — the business model seed artifact (industry, markets, value proposition, objectives)
- `context/glossary.md` — plain-language business term definitions (Condition B)
- `semantic/retail.ossie.yaml` — Ossie-standard semantic model (Condition C)
- `data/retail.duckdb` — generated output (binary, produced by `scripts/generate_data.py`, not hand-written)
- `evals/questions.md` — 20 graduated questions (5 per level × 4 levels)
- `evals/expected.md` — hand-verified expected SQL + answers, produced via `scripts/verify_expected.py`
- `CLAUDE.md` (project root) — neutral, condition-blind task prompt for the Claude Code sessions under test
- `evals/results/condition-a/`, `evals/results/condition-b/`, `evals/results/condition-c/` — output directories for each manual run (SQL + answer transcript + operator notes)
- `evals/results/comparison.md` — the Phase 1 findings write-up: scored table + documented failure modes per condition

### Relevant Documentation — read before implementing

- [Apache Ossie GitHub repo](https://github.com/apache/ossie) — the semantic layer standard this lab uses
  - [Ossie core spec](https://github.com/apache/ossie/blob/main/core-spec/spec.md) — the four building blocks: `datasets`, `fields`, `relationships`, `metrics`, and the `ai_context`/`instructions`/`synonyms` annotation fields
  - [`examples/tpcds_semantic_model.yaml`](https://github.com/apache/ossie/blob/main/examples/tpcds_semantic_model.yaml) — a real, complete example semantic model over a retail-style schema (TPC-DS). **Use this as the direct syntax template** for `semantic/retail.ossie.yaml` — same domain (retail), same shape (fact + dimension tables, relationships, metrics).
  - Why: Ossie is a real, versioned Apache standard (v0.1.1 released Jan 2026; spec currently at 0.2.0.dev0) with a specific YAML shape — do not invent a different YAML structure.
- [DuckDB "Create Synthetic Data" guide](https://duckdb.org/docs/stable/guides/snippets/create_synthetic_data)
  - Why: shows DuckDB-native and Python-UDF approaches (`range()`, hash functions, Faker via Python function API) for generating rows directly in DuckDB
- [Python Faker for DuckDB Fake Data Generation (MotherDuck)](https://motherduck.com/blog/python-faker-duckdb-exploration/)
  - Why: pattern for combining `faker` with DuckDB inserts; also flags known gotchas below

**Known gotchas from research (apply directly to `scripts/generate_data.py`):**
- Faker-generated fields are not automatically consistent with each other (e.g., a customer's country and their orders' country can drift) — explicitly derive dependent fields (order country = customer country) rather than generating them independently.
- Randomly generated IDs are not guaranteed unique — use sequential IDs (`customer_id = i`) rather than random IDs for primary keys.
- Avoid any realistic-looking sensitive identifiers (SSNs, real addresses) — use only synthetic names/emails from `faker`, no real PII patterns.

### Patterns to Follow

**Business-model-first generation order (PRD §6, §12 Phase 1):**
`context/company.yaml` (business model) → schema design (derived from the business model, specified below) → `scripts/generate_data.py` (data, derived from schema + anomaly design) → `semantic/retail.ossie.yaml` (semantic model, derived from schema) → `evals/questions.md` (questions, derived from schema + anomaly) → `evals/expected.md` (answers, derived by *querying* the generated data, never invented). Do not skip steps or generate data before the business model and schema are fixed.

**Condition isolation (PRD §6):** each condition is defined purely by which files exist in the visible repo/session, not by prompt wording. `CLAUDE.md`'s task instruction must be **identical** across all three conditions and must never mention "condition," "experiment," "Ossie," or "glossary" by name — just: "Answer the questions in evals/questions.md using the available data. For each question, provide the SQL used and the resulting answer."

**Blind evaluation:** run each condition in a **fresh** Claude Code session (no shared history) to avoid leakage between conditions.

**Deliberate semantic traps (this is what makes the experiment meaningful):**

| # | Trap | Mechanism | What a schema-only agent (Condition A) is expected to get wrong | What the Ossie definition (Condition C) resolves |
|---|------|-----------|---|---|
| 1 | Snapshot vs. current pricing | `order_items.unit_price`/`unit_cost` store the price **actually paid** at sale time; `product_price_history` stores how `products.unit_price`/`unit_cost` change over time | Joins to the *current* product price instead of the transaction-time snapshot, silently restating historical revenue at today's prices | `revenue`/`margin` metrics are explicitly defined over `order_items.unit_price`/`unit_cost`, never `product_price_history` |
| 2 | Slowly-changing dimension | `customer_segment_history` tracks a customer's segment over time (`valid_from`/`valid_to`); `segment` is not a static column on `customers` | Joins straight to a customer's *current* segment for historical questions (e.g. "revenue from VIP customers in Q1"), misattributing revenue earned before a segment change | Metric/join guidance ties segment lookups to the order's date via the validity window, not the customer's current state |
| 3 | Partial returns decoupled from order status | `returns` records returned quantity **at the order-item (line) grain**; `orders.status` only distinguishes `completed`/`cancelled` — a `completed` order can still have partially returned lines | Filters on `orders.status != 'cancelled'` and stops there, missing partially-returned quantity embedded in otherwise-completed orders — this is also the mechanism behind the France anomaly | `revenue`/`margin` net out `returns.quantity_returned` at the line level regardless of order-level status |
| 4 | Multi-currency | Orders are placed in local currency (`orders.currency`, `orders.fx_rate_to_eur` captured at order time); one market (Switzerland/CHF) is non-Eurozone alongside France/Germany/Belgium (EUR) | Sums `unit_price * quantity` across currencies without conversion, inflating or deflating cross-market totals | `revenue` metric explicitly applies `fx_rate_to_eur` before aggregation |
| 5 | Fan-out via split shipments | `shipments` is a separate 1-to-many fact from `orders` (an order can have multiple shipments due to split fulfillment); it must **not** sit on the join path to `order_items` | A naive `orders JOIN shipments JOIN order_items` multiplies line-item rows by shipment count, inflating revenue for any multi-shipment order | Ossie relationships document the correct join path (`order_items` joins `orders` and `returns` directly, never through `shipments`) |

Each trap must be represented by at least one row/case in the generated data (Phase 1b) and at least one eval question that specifically exercises it (Phase 1d), so the comparison write-up (Phase 1f) can attribute Condition C's wins to specific, named definitional details rather than vague "it did better."

---

## IMPLEMENTATION PLAN

### Phase 1a: Business model + schema design

**Tasks:**
- Define the synthetic company in `context/company.yaml`: industry = specialty retail, markets = France/Germany/Belgium/Switzerland (Switzerland deliberately non-Eurozone, see Trap 4), value proposition = curated products + fast delivery, objectives = profitable growth + customer retention
- Design the retail schema on paper (see exact spec in Step-by-Step Tasks below) before writing generation code: `customers`, `customer_segment_history`, `products`, `product_price_history`, `orders`, `order_items`, `returns`, `shipments` — 8 tables total, incorporating the 5 deliberate traps listed above
- Design the deliberate anomaly: a traceable France revenue decline in one quarter caused by a spike in **partial, line-grain returns** (Trap 3) driven by a fulfillment delay — `orders.status` stays `completed` for these orders, so the anomaly is only correctly explained once returns are netted at the line level. This must be reconstructible from raw data alone (Condition A can theoretically find it by noticing the `returns` table) but is expected to be missed or under-computed without the Ossie `revenue`/`margin` definitions (Condition C)

### Phase 1b: Data generation

**Tasks:**
- Implement `scripts/generate_data.py` using `duckdb` + `faker`, fixed seed (e.g. `Faker.seed(42)`, `random.seed(42)`)
- Generate all 8 tables per the schema (Step-by-Step Tasks below), embedding all 5 deliberate traps and the France anomaly
- Write `data/retail.duckdb` via `duckdb.connect("data/retail.duckdb")`
- Implement `tests/test_generated_data.py`: row counts within expected ranges, referential integrity across every FK (including the two SCD history tables and `returns`/`shipments`), and explicit assertions that each of the 5 traps is actually present and detectable in the generated data (not just theoretically possible) — see the CREATE task for this file below for the exact assertions

### Phase 1c: Context layer artifacts

**Tasks:**
- Write `context/glossary.md` — plain-language definitions for: revenue, margin, return, customer segment, order, discount, shipment. Deliberately silent on the 5 traps' precise resolution (see CREATE task below) so Condition B is genuinely weaker than Condition C, not a duplicate.
- Write `semantic/retail.ossie.yaml` — Ossie v0.2.0.dev0-style YAML with `datasets` (all 8 tables), `relationships` (including the documented **non-join-path** warning for `shipments`, Trap 5), and `metrics` (`revenue`, `margin`, `order_count`, `average_order_value`, `return_rate`) that correctly resolve all 5 traps, following the syntax in `examples/tpcds_semantic_model.yaml`
- Verify each trap is resolved by name in the Ossie file: `revenue`/`margin` reference `order_items.unit_price`/`unit_cost` (not `product_price_history`, Trap 1), net out `returns.quantity_returned` at line grain regardless of `orders.status` (Trap 3), apply `fx_rate_to_eur` (Trap 4), and the `relationships` section documents that `order_items` must join `orders`/`returns` directly and never through `shipments` (Trap 5) — these are the specific definitional details Condition C is supposed to get right that Conditions A/B are expected to miss or get inconsistently

### Phase 1d: Eval set

**Tasks:**
- Write `evals/questions.md`: 5 questions per level (20 total) per PRD §5/§7 framing, with **each of the 5 traps exercised by at least one question**:
  - Level 1 (data lookup): e.g. total revenue by country (Trap 4, currency), top product category by units sold, average order value in a given quarter (Trap 1, snapshot pricing — must not use current product price), order count in a date range, total shipments sent to Belgium
  - Level 2 (business "why"): e.g. why did net revenue in France decline in [anomaly quarter] (Trap 3, line-grain returns despite `completed` status); what share of revenue came from customers who were VIP segment *at the time of purchase* in Q1 (Trap 2, SCD)
  - Level 3 (policy): e.g. could discounts increase for French customers without dropping margin below 20% (requires correct net revenue/margin, Traps 1+3); is average revenue per shipment declining for orders with split fulfillment (Trap 5, fan-out risk if joined naively)
  - Level 4 (action/optimization): e.g. identify customers where a discount would increase revenue while keeping margin above 20%, correctly across all four markets (Traps 1+3+4 combined)
- Run `scripts/verify_expected.py` against `data/retail.duckdb` for every question, capture the real SQL + real result, and write both into `evals/expected.md` — do not hand-type expected answers

### Phase 1e: Neutral task prompt

**Tasks:**
- Write `CLAUDE.md` at the repo root with only the neutral task instruction (see Patterns to Follow above) plus minimal orientation (where the DuckDB file is, that SQL should be shown for each answer) — no mention of conditions or the experiment's purpose

### Phase 1f: Manual condition runs + scoring

**Tasks:**
- Condition A: temporarily hide/remove `context/` and `semantic/` from what's visible to the session (e.g., run from a clean checkout or clone with only `data/`, `evals/questions.md`, `CLAUDE.md` present); fresh Claude Code session; save transcript to `evals/results/condition-a/`
- Condition B: same as A, plus `context/glossary.md` visible; save to `evals/results/condition-b/`
- Condition C: same as A, plus `semantic/retail.ossie.yaml` visible; save to `evals/results/condition-c/`
- Score each condition's 20 answers against `evals/expected.md` (pass/fail) and record the specific failure mode per miss (wrong filter, wrong join, hallucinated column, wrong metric definition, etc.)
- Write `evals/results/comparison.md`: scored table (question × condition → pass/fail) + failure-mode narrative, explicitly calling out at least one case where Condition C succeeds because of the Ossie `revenue` definition and Condition A/B do not

---

## STEP-BY-STEP TASKS

Execute in order, top to bottom.

### CREATE `pyproject.toml`

- **IMPLEMENT**: `[project]` with `name = "ossie-lab"`, `requires-python = ">=3.11"`, `dependencies = ["duckdb>=1.0", "faker>=25.0"]`, `[project.optional-dependencies] dev = ["pytest>=8.0", "ruff>=0.5"]`
- **VALIDATE**: `python -c "import tomllib; tomllib.load(open('pyproject.toml','rb'))"`

### CREATE `context/company.yaml`

- **IMPLEMENT**: business model seed — `company.industry: specialty_retail`, `company.markets: [France, Germany, Belgium, Switzerland]`, `company.currency_note: "Switzerland uses CHF; all other markets use EUR"`, `company.value_proposition: [curated_products, fast_delivery]`, `company.objectives: [profitable_growth, customer_retention]`, `company.kpis: [revenue, margin, return_rate, vip_customer_share]`, `company.priorities: [reduce_return_rate_in_underperforming_markets, grow_vip_segment]`
- **GOTCHA**: this file is read by a human at generation time, not by the agent under test in any condition — it seeds schema/data design, it is not one of the three condition files
- **FORWARD-COMPATIBILITY**: write `objectives`/`kpis`/`priorities` at the level of detail a real `business/` context file (PRD §6 business context layer) would need, even though this file plays no role in Conditions A/B/C. The France-anomaly narrative should trace directly to one of these priorities (e.g. `reduce_return_rate_in_underperforming_markets`) so Phase 2/3 can lift this content into a proper business-context artifact largely as-is, rather than rewriting it from scratch.
- **VALIDATE**: `python -c "import yaml; yaml.safe_load(open('context/company.yaml'))"`

### CREATE `scripts/lib/synthetic_traps.py`

- **IMPLEMENT**: a domain-agnostic library, importable by any future domain recipe, exposing:
  - `generate_scd2_history(entity_ids, value_generator_fn, transition_rate, start_date, end_date, rng) -> list[dict]` — produces `{entity_id, valid_from, valid_to, **attrs}` rows for a slowly-changing attribute (used for both `product_price_history` and `customer_segment_history` in the retail recipe — Traps 1 & 2 are the *same function*, called twice with different `value_generator_fn`/`transition_rate`)
  - `snapshot_as_of(history_rows, entity_id, as_of_date) -> dict` — point-in-time lookup (`valid_from <= as_of_date < COALESCE(valid_to, max_date)`), used both by the recipe when generating transaction rows and available for reuse in verification/eval code
  - `generate_child_reversal(parent_rows, reversal_rate, reversal_amount_fn, rng, anomaly_subset=None, anomaly_rate=None) -> list[dict]` — produces partial-reversal rows against a parent fact at child grain (used for `returns`, Trap 3); `anomaly_subset`/`anomaly_rate` let a caller inject an elevated-rate anomaly for a specific subset (e.g. one country × one quarter) without a separate code path
  - `generate_fx_rates(currencies, base_currency, date_range, rng, noise_pct=0.02) -> dict[(currency, date), float]` — plausible FX rates with small realistic noise (Trap 4); `base_currency` rate is always `1.0`
  - `generate_fanout_fact(parent_ids, min_children, max_children, multi_rate, rng) -> list[dict]` — produces `{parent_id, child_id}` rows for an auxiliary 1:N fact where a `multi_rate` fraction of parents get 2+ children (used for `shipments`, Trap 5)
- **GOTCHA**: none of these functions may reference `customer`, `product`, `order`, or any retail-specific name — they operate on generic `entity_id`/`parent_id`/dict-of-attributes only. If a retail-specific name leaks into this file, the reusability goal is broken.
- **PATTERN**: pure functions taking an explicit `rng` (e.g. `random.Random(seed)` instance, not global `random.seed()`) so the retail recipe and future domain recipes can each seed independently without interfering with each other
- **VALIDATE**: `python -c "from scripts.lib.synthetic_traps import generate_scd2_history, snapshot_as_of, generate_child_reversal, generate_fx_rates, generate_fanout_fact"`

### CREATE `tests/test_synthetic_traps.py`

- **IMPLEMENT**: unit tests against a toy domain that is **not** retail (e.g. generic `widget`/`owner` entities) to prove the library has no retail coupling: SCD2 history produces non-overlapping, gapless validity windows per entity; `snapshot_as_of` returns the correct row for dates on either side of a transition; `generate_child_reversal`'s `anomaly_subset` measurably elevates the rate only for the targeted subset; `generate_fanout_fact` produces the requested `multi_rate` proportion of multi-child parents within a reasonable tolerance
- **VALIDATE**: `pytest tests/test_synthetic_traps.py -v`

### CREATE `scripts/generate_data.py`

- **IMPLEMENT**: the retail-specific recipe — defines retail's 8 tables/columns and calls into `scripts/lib/synthetic_traps.py` for each of the 5 traps (see mapping in the library task above) rather than reimplementing SCD/reversal/FX/fan-out logic inline. Generate 8 tables into `data/retail.duckdb`, in dependency order:
  - `customers(customer_id INT PK, name, email, country, signup_date)` — ~300 rows across France/Germany/Belgium/Switzerland. No `segment` column here — segment is time-varying, see below (Trap 2).
  - `customer_segment_history(customer_id FK, segment ENUM['standard','VIP'], valid_from DATE, valid_to DATE NULL)` — every customer starts `standard`; ~15% are promoted to `VIP` at a random later date (new row with `valid_from` = promotion date, previous row's `valid_to` set to the same date). Current segment = row where `valid_to IS NULL`.
  - `products(product_id INT PK, name, category, subcategory)` — ~50 rows, 5-6 categories. No price/cost columns here — see below (Trap 1).
  - `product_price_history(product_id FK, unit_price DECIMAL, unit_cost DECIMAL, valid_from DATE, valid_to DATE NULL)` — initial price/cost per product at company launch date; ~20% of products get exactly one price change (both `unit_price` and `unit_cost` shift) at a random later date, closing out the prior row's `valid_to`.
  - `orders(order_id INT PK, customer_id FK, order_date DATE, country, currency ENUM['EUR','CHF'], fx_rate_to_eur DECIMAL, status ENUM['completed','cancelled'])` — ~2000 rows spanning 4-6 quarters. `country`/`currency` derived from the customer's country (`Switzerland` → `CHF`, others → `EUR`); `fx_rate_to_eur` = 1.0 for EUR orders, a plausible fixed rate (e.g. ~0.96) with small realistic noise for CHF orders on that `order_date`.
  - `order_items(order_item_id INT PK, order_id FK, product_id FK, quantity INT, unit_price DECIMAL, unit_cost DECIMAL, line_discount_pct DECIMAL)` — 1-4 rows per order. `unit_price`/`unit_cost` **must be looked up from `product_price_history` as of `order_date`** (the row where `valid_from <= order_date < COALESCE(valid_to, '9999-12-31')`), never copied from a "current price" concept — this is what makes Trap 1 real in the data, not just theoretical.
  - `returns(return_id INT PK, order_item_id FK, return_date DATE, quantity_returned INT, reason)` — sparse table (~10% of order_items have a partial return in normal conditions). `orders.status` for these stays `completed` — returns are tracked at line grain only, never by flipping order status.
  - `shipments(shipment_id INT PK, order_id FK, ship_date DATE, carrier)` — ~85% of orders get exactly 1 shipment; ~15% get 2-3 shipments (split fulfillment) to make Trap 5 (fan-out) concretely reproducible via a naive join.
  - Embed the anomaly: in one specific quarter, France `order_items` have a materially higher `quantity_returned` rate than other quarter/country combinations (e.g. ~35% of quantity returned vs. baseline ~8%), simulating a fulfillment-delay-driven return spike — inserted via extra rows in `returns`, with `orders.status` unchanged (`completed`)
- **PATTERN**: `Faker.seed(42)` for name/email fields plus one explicit `random.Random(42)` instance passed into every `synthetic_traps` library call (not global `random.seed()`) for reproducibility; use sequential integer IDs, not random IDs, for primary keys
- **IMPORTS**: `duckdb`, `faker.Faker`, `datetime`, and `from scripts.lib.synthetic_traps import generate_scd2_history, snapshot_as_of, generate_child_reversal, generate_fx_rates, generate_fanout_fact`
- **GOTCHA 1**: generate rows in Python/pandas-like structures first, then bulk-insert into DuckDB (e.g. via `duckdb.sql` on a Python list-of-dicts or `duckdb.register` a DataFrame) rather than row-by-row `INSERT` for performance
- **GOTCHA 2**: generation order matters — `product_price_history` and `customer_segment_history` must exist before `orders`/`order_items` are generated, since `order_items.unit_price`/`unit_cost` and any point-in-time segment lookups depend on them
- **GOTCHA 3**: this file should read as a *thin recipe* — table/column names, row counts, and business parameters (transition rates, currencies) live here; the actual SCD/reversal/FX/fan-out mechanics must not be reimplemented here (they live in `scripts/lib/synthetic_traps.py`). If you find yourself writing validity-window logic or reversal-rate logic directly in this file, stop and move it to the library instead.
- **VALIDATE**: `python scripts/generate_data.py && python -c "import duckdb; c=duckdb.connect('data/retail.duckdb'); print(c.sql('SELECT count(*) FROM orders').fetchone(), c.sql('SELECT count(*) FROM returns').fetchone(), c.sql('SELECT count(*) FROM shipments').fetchone())"`

### CREATE `tests/test_generated_data.py`

- **IMPLEMENT**: pytest tests covering:
  - Row count ranges for all 8 tables
  - Referential integrity via `LEFT JOIN ... WHERE right.id IS NULL` returning 0 rows for every FK, including `order_items → returns`, `orders → shipments`, `customer_segment_history → customers`, `product_price_history → products`
  - Trap 1 present: at least one product has 2+ rows in `product_price_history` (a real price change occurred)
  - Trap 2 present: at least one customer has 2+ rows in `customer_segment_history` (a real segment promotion occurred)
  - Trap 3 / anomaly present: return rate (`SUM(quantity_returned)/SUM(quantity)`) in the anomaly quarter for France exceeds 25%, while all other country/quarter combinations stay under 15%, **and** `orders.status = 'completed'` for the affected orders (confirms the anomaly is invisible to an order-status-only filter)
  - Trap 4 present: at least one order has `currency = 'CHF'` and `fx_rate_to_eur != 1.0`
  - Trap 5 present: at least one order has 2+ rows in `shipments`
- **PATTERN**: standard `pytest` fixture connecting to `data/retail.duckdb` read-only
- **VALIDATE**: `pytest tests/test_generated_data.py -v`

### CREATE `semantic/retail.ossie.yaml`

- **IMPLEMENT**: Ossie v0.2.0.dev0-shaped YAML with top-level `version: "0.2.0.dev0"` and `semantic_model:` containing `name`, `description`, `datasets:` for all 8 tables (each with `source`, `primary_key`, `fields`), `relationships:` covering:
  - `orders → customers` via `customer_id`
  - `order_items → orders` via `order_id`
  - `order_items → products` via `product_id`
  - `order_items → returns` via `order_item_id` (nullable — not every line has a return)
  - `orders → shipments` via `order_id`, with an explicit `ai_context`/`description` note: *"shipments is for fulfillment tracking only — do not join through shipments to compute order or line-item metrics; joining orders→shipments→order_items will duplicate line-item rows once per shipment"* (this is the Trap 5 documentation)
  - `product_price_history → products` and `customer_segment_history → customers`, each with an `ai_context` note that these are point-in-time tables and must be filtered to the relevant date, not treated as 1:1 dimensions
  - `metrics:`
    - `revenue`: nets `order_items.quantity - COALESCE(returns.quantity_returned, 0)` × `order_items.unit_price` × `(1 - order_items.line_discount_pct)`, converted via `orders.fx_rate_to_eur`, filtered to `orders.status = 'completed'`, joined only through `order_items → orders` and `order_items → returns` (never `shipments`)
    - `margin`: same net-quantity/FX logic as `revenue`, using `order_items.unit_cost` instead of `unit_price`, expressed as `(revenue - net_cost) / revenue`
    - `order_count`: `COUNT(DISTINCT orders.order_id)` filtered to `completed`
    - `average_order_value`: `revenue / order_count`
    - `return_rate`: `SUM(returns.quantity_returned) / SUM(order_items.quantity)`
- **PATTERN**: mirror the exact YAML shape from [`examples/tpcds_semantic_model.yaml`](https://github.com/apache/ossie/blob/main/examples/tpcds_semantic_model.yaml) (dataset → fields → expression.dialects[ANSI_SQL] structure; relationships with `from`/`to`/`from_columns`/`to_columns`; metrics with `expression.dialects` and `description`)
- **GOTCHA**: every one of the 5 traps in the table under Patterns to Follow must be traceable to a specific line in this file — the `revenue`/`margin` expressions resolve Traps 1, 3, 4; the `relationships` `ai_context` notes resolve Traps 2 and 5. This file is the single artifact Condition C gets that A/B don't, so it must carry the full definitional weight of the experiment.
- **VALIDATE**: `python -c "import yaml; d=yaml.safe_load(open('semantic/retail.ossie.yaml')); s=str(d); assert 'completed' in s and 'fx_rate_to_eur' in s and 'quantity_returned' in s and 'shipments' in s"`

### CREATE `context/glossary.md`

- **IMPLEMENT**: plain-language definitions (no SQL) for revenue, margin, return, customer segment, order, discount, shipment — written at the level of business-user language, deliberately *less* precise than the Ossie file on all 5 traps. E.g.: "Revenue is the money we make from completed sales" (doesn't mention netting partial returns, Trap 3); "A customer's segment is either standard or VIP" (doesn't mention segments change over time, Trap 2); no mention of currency conversion, snapshot pricing, or the shipments fan-out risk at all. This keeps Condition B a genuinely different (weaker) context than Condition C, not a duplicate.
- **VALIDATE**: manual read-through — confirm none of the 5 trap resolutions from the Ossie file (line-level return netting, FX conversion, snapshot pricing, point-in-time segment, shipments join warning) are present in this file

### CREATE `evals/questions.md`

- **IMPLEMENT**: 20 questions, numbered, grouped by level (see Phase 1d task list above for concrete examples); each question references only business language, never table/column names directly; confirm each of the 5 traps (snapshot pricing, SCD segment, line-grain returns, multi-currency, shipment fan-out) is exercised by at least one question, and note in an inline comment (or a small mapping table at the top of the file) which question targets which trap, for use when writing the Phase 1f comparison
- **VALIDATE**: manual count — exactly 5 questions per level, 20 total, and all 5 traps represented at least once

### CREATE `scripts/verify_expected.py`

- **IMPLEMENT**: a script with one hardcoded SQL query per question in `evals/questions.md`, executed against `data/retail.duckdb`, printing `question_id | sql | result` for the operator to transcribe into `evals/expected.md`
- **VALIDATE**: `python scripts/verify_expected.py` runs without error and prints 20 results

### CREATE `evals/expected.md`

- **IMPLEMENT**: for each of the 20 questions, the verified SQL and the exact result from `scripts/verify_expected.py` output — transcribed, not retyped from memory
- **VALIDATE**: spot-check 3 random questions by re-running their SQL manually against `data/retail.duckdb` and confirming the answer matches

### CREATE `CLAUDE.md` (repo root)

- **IMPLEMENT**: minimal, neutral orientation + the fixed task instruction: "This repo contains a DuckDB database at `data/retail.duckdb`. Answer the questions in `evals/questions.md` using the available data. For each question, provide the SQL query used and the resulting answer." Nothing else — no mention of Ossie, glossary, or the experiment.
- **GOTCHA**: do not describe the experiment, the conditions, or the semantic model in this file — that would leak the condition to the agent under test
- **VALIDATE**: manual read-through for neutrality (no leaked condition info)

### RUN Condition A (schema only)

- **IMPLEMENT**: prepare a working copy with only `data/`, `evals/questions.md`, `CLAUDE.md` present (e.g. `git worktree add` or a filtered copy with `context/` and `semantic/` removed); start a fresh Claude Code session there; give it the task; save the full transcript (questions, SQL, answers) to `evals/results/condition-a/transcript.md`
- **VALIDATE**: `evals/results/condition-a/transcript.md` contains 20 answered questions with SQL for each

### RUN Condition B (schema + glossary)

- **IMPLEMENT**: same as Condition A but with `context/glossary.md` also present; fresh session; save to `evals/results/condition-b/transcript.md`
- **VALIDATE**: same as Condition A

### RUN Condition C (schema + Ossie)

- **IMPLEMENT**: same as Condition A but with `semantic/retail.ossie.yaml` also present; fresh session; save to `evals/results/condition-c/transcript.md`
- **VALIDATE**: same as Condition A

### CREATE `evals/results/comparison.md`

- **IMPLEMENT**: a 20×3 scored table (pass/fail per question per condition) built by comparing each transcript's answers to `evals/expected.md`, followed by a failure-mode narrative section, explicitly identifying at least one question where Condition C passes specifically due to the `revenue` metric's completed-order filter and Condition A/B fail or are inconsistent
- **VALIDATE**: manual review against PRD §11 success criteria — confirm the write-up documents "why," not just pass/fail counts

---

## TESTING STRATEGY

This is a data/eval lab, not an application with user-facing flows — testing is split between (1) automated sanity checks on the generated dataset, and (2) the manual eval scoring process itself, which *is* the feature's validation.

### Unit Tests

`tests/test_generated_data.py` (pytest): row-count sanity ranges, referential integrity across all FK relationships, and explicit verification that the deliberate France-return-rate anomaly is present and measurable in the generated data.

### Integration Tests

`scripts/verify_expected.py` acts as an integration check: it re-derives every expected answer directly from the live DuckDB file, so a schema or data-generation change that breaks a question's assumptions is caught by re-running it (result changes or query errors) before `evals/expected.md` is finalized.

### Edge Cases

- Orders with zero `order_items` rows (should not happen — assert in `test_generated_data.py`)
- A country/quarter combination with zero orders (should not happen given ~2000 orders across 4 countries and 4-6 quarters, but guard against division-by-zero in `average_order_value`/`margin` if it does)
- The anomaly quarter must be unambiguous — only one quarter should show the elevated France return rate, so Level 2 "why" questions have a single defensible answer
- A product with a price change (Trap 1) must have orders both before and after the change date, so questions spanning that boundary have a real, checkable difference between "price paid" and "current price"
- A customer with a segment promotion (Trap 2) must have orders both before and after the promotion date, for the same reason
- An order with 2+ shipments (Trap 5) must also have 2+ order_items, so a naive `orders JOIN shipments JOIN order_items` on that order visibly multiplies rows (e.g. 2 shipments × 3 items = 6 rows instead of 3) — this must be verifiable directly in DuckDB, not just theoretical

### E2E / Browser Automation

**Not applicable.** This feature has no UI and no web-facing flow; the `agent-browser` skill does not apply. The equivalent end-to-end validation is the three manual Claude Code condition runs (Phase 1f) — this replaces Level 5 below.

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style

```bash
ruff check scripts/ tests/
python -c "import yaml; yaml.safe_load(open('context/company.yaml')); yaml.safe_load(open('semantic/retail.ossie.yaml'))"
```

### Level 2: Unit Tests

```bash
pytest tests/test_synthetic_traps.py -v
python scripts/generate_data.py
pytest tests/test_generated_data.py -v
```

### Level 3: Integration Tests

```bash
python scripts/verify_expected.py
```

Manually diff the printed output against what's transcribed in `evals/expected.md` — every question's SQL result must match exactly.

### Level 4: Manual Validation

- Confirm `evals/questions.md` has exactly 20 questions, 5 per level, and all 5 traps represented
- Confirm `context/glossary.md` does not leak any of the 5 trap resolutions (should be strictly less precise than the Ossie file on pricing snapshots, segment history, return netting, currency conversion, and shipment joins)
- Confirm `semantic/retail.ossie.yaml` parses and its `revenue`/`margin` expressions contain the completed-order filter, the return-quantity netting, and the FX conversion, and its `relationships` section documents the shipments non-join-path warning
- Confirm `CLAUDE.md` contains no mention of "condition," "experiment," "Ossie," or "glossary"
- Run the 5 trap-presence checks directly (e.g. `duckdb data/retail.duckdb "SELECT product_id, count(*) FROM product_price_history GROUP BY 1 HAVING count(*) > 1"`, and equivalents for the other 4 traps) to confirm each trap is not just asserted in tests but manually inspectable

### Level 5: Manual Condition Runs (replaces browser E2E for this feature)

```bash
# Condition A — schema only
git worktree add ../ossie-lab-condition-a
cd ../ossie-lab-condition-a && rm -rf context semantic
# start a fresh Claude Code session here, run the CLAUDE.md task, save transcript

# Condition B — schema + glossary
git worktree add ../ossie-lab-condition-b
cd ../ossie-lab-condition-b && rm -rf semantic
# fresh session, save transcript

# Condition C — schema + Ossie
git worktree add ../ossie-lab-condition-c
cd ../ossie-lab-condition-c && rm -rf context
# fresh session, save transcript
```

Save each transcript to `evals/results/condition-{a,b,c}/transcript.md` in the main repo, then remove the worktrees (`git worktree remove ../ossie-lab-condition-a`, etc.).

### Level 6: Additional Validation

None required — no MCP servers or external services involved in Phase 1.

---

## ACCEPTANCE CRITERIA

- [ ] `scripts/lib/synthetic_traps.py` contains no retail-specific names and passes `tests/test_synthetic_traps.py` against the toy domain
- [ ] `data/retail.duckdb` generates deterministically (same seed → same data) via `scripts/generate_data.py` calling into the library, and passes all `tests/test_generated_data.py` checks, including the 5 trap-presence assertions
- [ ] `semantic/retail.ossie.yaml` parses as valid YAML and follows the Ossie `datasets`/`relationships`/`metrics` structure from the reference example, and resolves all 5 traps by name
- [ ] `evals/questions.md` has exactly 20 questions, 5 per level (data/business/policy/action), covering all 5 traps
- [ ] `evals/expected.md` answers are all derived from `scripts/verify_expected.py` output, not hand-typed
- [ ] `CLAUDE.md` task prompt is identical in spirit and wording across all three condition runs and contains no condition-identifying language
- [ ] All three conditions (A, B, C) have been run in fresh Claude Code sessions with transcripts saved
- [ ] `evals/results/comparison.md` contains a scored table and a failure-mode narrative, with each of the 5 traps individually attributed to at least one question showing Condition C succeeding where A/B fail or are inconsistent
- [ ] No regressions: `pyproject.toml` installs cleanly (`pip install -e ".[dev]"`) in a clean environment

## COMPLETION CHECKLIST

- [ ] All tasks completed in order (1a → 1f)
- [ ] Each task's validation command passed immediately after implementation
- [ ] `ruff check` and YAML parse checks pass with zero errors
- [ ] `pytest tests/` passes fully
- [ ] `scripts/verify_expected.py` output matches `evals/expected.md` exactly
- [ ] All three manual condition runs completed with saved transcripts
- [ ] `evals/results/comparison.md` written and reviewed against PRD §11 success criteria
- [ ] Acceptance criteria above all met

---

## NOTES

- **Why Python + DuckDB + Faker, not a different stack**: the PRD names DuckDB explicitly as the query engine; Python + `duckdb` + `faker` is the documented, idiomatic combination for this per the [DuckDB synthetic data guide](https://duckdb.org/docs/stable/guides/snippets/create_synthetic_data) and [MotherDuck's Faker/DuckDB writeup](https://motherduck.com/blog/python-faker-duckdb-exploration/), and keeps the whole lab dependency-light and local, matching PRD §9 (no external services).
- **Why Ossie's TPC-DS example is the syntax reference**: it's a real, retail-domain, fact/dimension-table example shipped by the Apache Ossie project itself — using it as the template minimizes the risk of inventing an incorrect YAML shape for a standard that's still at `0.2.0.dev0` and evolving.
- **Why the glossary must be deliberately less precise than Ossie**: if `glossary.md` and `retail.ossie.yaml` encode the same precision, Condition B and Condition C become indistinguishable and the experiment can't isolate the semantic layer's specific contribution (PRD §14 risk: "conditions score equally, no signal").
- **Why the schema was expanded from 4 flat tables to 8 with 5 deliberate traps**: the original design (customers/products/orders/order_items, single price, single currency, order-level status) is too simple to genuinely test semantic-layer value — a schema-only agent has a reasonable chance of guessing correctly by luck, which would produce a false negative ("semantic layers don't matter"). The 5 traps added — snapshot-vs-current pricing, a slowly-changing customer-segment dimension, line-grain partial returns decoupled from order status, multi-currency conversion, and a fan-out risk via split shipments — are standard, well-documented dimensional-modeling failure modes (the kind any real BI/semantic-layer tool exists to solve). Each has a concrete, checkable "wrong answer" a naive SQL query produces and a concrete "right answer" only available once the Ossie definitions supply the missing join/filter/conversion logic. This turns "does the semantic layer help?" from a vague impression into 5 falsifiable, individually attributable test cases.
- **Domain-agnostic pattern catalog (for Phase 3, not built now)**: the 5 traps are retail-specific *instances* of generic dimensional-modeling patterns that recur in any business domain. Recording the mapping here so Phase 3's business-model-first generator has a concrete starting catalog to parameterize rather than re-deriving these from scratch:

  | Trap (retail instance) | Domain-agnostic pattern | Other domains it shows up in |
  |---|---|---|
  | Product price history | Slowly-changing reference attribute (SCD Type 2) on a dimension | SaaS pricing tiers, insurance premium rates, employee salary bands |
  | Customer segment history | Same SCD Type 2 pattern, different dimension | User plan tier, patient risk category, loan credit grade |
  | Line-grain partial returns | Child-grain reversal/adjustment decoupled from parent-record status | Partial refunds, partial shipment cancellations, insurance claim adjustments |
  | Multi-currency | Unit conversion applied at transaction time, not query time | Multi-region pricing, imperial/metric conversions, per-market tax rates |
  | Shipment fan-out | Auxiliary 1:N fact at a different grain than the metric's base fact, wrongly placed on the join path | Login/event logs, support tickets, delivery attempts — any "tracking" table that shouldn't sit between a fact and its dimensions |

  Phase 3 generalization should treat "pick N traps from this catalog and instantiate them for domain X's entities" as the reusable mechanism, rather than hand-designing new traps per domain from scratch. Do not build the generator itself in Phase 1 — this catalog is documentation only.
- **Why business context isn't a 4th Phase 1 condition**: the PRD's context layer names business context (goals/KPIs/priorities) as a layer distinct from the semantic layer. Promoting `context/company.yaml` to an agent-visible condition now would turn the clean 3-way A/B/C comparison into a 4-way one before the core hypothesis (does *any* semantic layer help) is validated — PRD Phase 2 already scopes this properly as Conditions D/E once a `knowledge/` layer exists. `context/company.yaml` stays a human-only generation seed in Phase 1, but per the FORWARD-COMPATIBILITY note above, it's written with enough detail (objectives/KPIs/priorities, not just industry/markets) to be lifted into a real business-context artifact later with minimal rework.
- **Why the generation code is a library, not a skill or subagent**: reusability here means "the same 5 trap mechanisms are callable for a different domain without rewriting them," which is a code-structure problem, not an agent-orchestration problem. A subagent is the wrong mechanism — subagents delegate reasoning/search within a session, they don't own persistent reusable code. A skill (e.g. a future `/generate-synthetic-enterprise`) is the *right eventual* mechanism for orchestrating "pick a domain → design a business model → pick traps from the catalog → generate data → write the semantic model," but that's the Phase 3 business-model-first generator, which needs LLM-driven business-model design and human validation gates (PRD §6/§12 Phase 3) — building that orchestration now, before Phase 1 has produced a result, is exactly the "over-engineered before proven necessary" risk PRD §14 already flags. The cheap, low-risk move available now is factoring the deterministic trap-generation logic into `scripts/lib/synthetic_traps.py` (domain-agnostic, unit-tested against a non-retail toy domain) so that whatever eventually orchestrates Phase 3 — a skill, a script, or a human — calls the same 5 functions instead of reimplementing SCD/reversal/FX/fan-out logic from scratch.
- **Deferred to Phase 2 (do not build now)**: `knowledge/` policy docs, Conditions D/E, the `/run-eval` automation skill. Deferred to Phase 3: the general business-model-first generator (as a skill, using `scripts/lib/synthetic_traps.py` and the pattern catalog above), process context layer.
- **Confidence score: 7/10** for one-pass success on the mechanical parts (schema, data generation, Ossie YAML, questions/expected answers) — these are fully specified but the added trap complexity (point-in-time joins for SCD tables, correct FX/return netting in generation code) has more moving parts than the original 4-table design, so budget extra time for `tests/test_generated_data.py` to fail and need iteration on the generator before all 5 trap assertions pass. The manual condition-run scoring (Phase 1f) still inherently depends on what Claude Code actually produces in each session, which cannot be predicted in advance.
