---
name: run-eval
description: Run one Context Layer Lab condition (A-E) end to end — launch the matching MCP question-server, spawn a fresh condition-blind agent against it, export the run, and score it against evals/expected.md. Use when asked to "run condition X", "run the eval", or "score condition X".
---

# /run-eval

Automates the Phase 1 manual loop (git worktree → fresh session → transcript →
hand-score) using the MCP question-server built in Phase 2 (`question_server/`).
Condition isolation now lives at the server boundary, not the filesystem: one
server process is launched bound to exactly one condition's context files
(`evals/conditions.yaml`), and the agent under test only ever sees that
server's tool calls — never a condition letter, a file it shouldn't have, or
this conversation's own context.

**Read [`PRD.md`](../../../PRD.md) §7/§10 (MCP question-server) and
[`evals/conditions.yaml`](../../../evals/conditions.yaml) before running this
if you haven't already** — they define the contract this skill automates.

## Arguments

`--condition <A|B|C|D|E>` (required), `--run-id <id>` (optional, defaults to
`<condition>-<UTC timestamp>`).

## Steps

1. **Resolve the Python interpreter.** Use the same interpreter the project's
   tests run under (check for a project venv first; this repo currently uses
   `C:\Users\franc\anaconda3\python.exe` — confirm with
   `<python> -c "import duckdb, mcp, yaml"` before proceeding, and stop with a
   clear message if any import fails rather than guessing).

2. **Generate the run id** if not supplied, and confirm
   `evals/results/runs/<run_id>.json` does not already exist (fail rather than
   silently overwrite a prior run).

3. **Write a scoped MCP config** to a temp file (e.g.
   `evals/results/runs/.mcp-<run_id>.json`):
   ```json
   {
     "mcpServers": {
       "ossie-lab": {
         "command": "<python>",
         "args": ["-m", "question_server", "--condition", "<CONDITION>", "--run-id", "<run_id>"],
         "cwd": "<repo root>"
       }
     }
   }
   ```
   This file is the *only* place the condition letter is written down for
   this run — never put it in the task prompt.

4. **Compose the condition-blind task prompt.** Do not reuse `CLAUDE.md`
   verbatim — that file governs the Phase 1 worktree process, whose answer
   format (fenced markdown SQL blocks) doesn't apply here. Use instead:

   > This lab exposes a set of MCP tools for exploring a retail database and
   > answering business questions. Call `list_questions` to see the question
   > set, `get_schema` and `get_context_bundle` to understand what data and
   > context are available, `query_database` to run read-only SQL, and
   > `submit_answer(question_id, sql, answer)` once per question to record
   > your final answer. Answer every question returned by `list_questions`.

   This prompt is identical for every condition by construction — it never
   mentions which tools return what, only that they exist, so an agent
   working under Condition A (empty `get_context_bundle`) and one working
   under Condition E (full bundle) receive the same instructions and differ
   only in what the tools actually return.

5. **Spawn a fresh, isolated agent against that config.** Two supported
   mechanisms — pick whichever is available in the current environment and
   say which one you used in the run summary:
   - **Preferred: headless CLI.** Shell out to
     `claude -p "<task prompt>" --mcp-config <config path> --strict-mcp-config --allowedTools "mcp__ossie-lab__*"`
     (flag names may differ by installed Claude Code version — run
     `claude --help` first and adjust rather than assuming). This is a truly
     fresh process with no access to this conversation, which is the
     strongest available isolation guarantee.
   - **Fallback: `Agent` tool.** If `claude` isn't invokable from the current
     shell, use the `Agent` tool with a `general-purpose` subagent and the
     same task prompt. This is weaker isolation (the subagent still shares
     this session's general tool access) — note this explicitly in the run
     summary rather than silently treating it as equivalent to the headless
     path.
   Capture stdout to `evals/results/condition-<x>/transcript-<run_id>.txt` as
   a human-readable record — this is evidence, not the scoring input; scoring
   reads the structured run log the server already wrote via `submit_answer`.

6. **Delete the temp MCP config** (`evals/results/runs/.mcp-<run_id>.json`) —
   it's the only condition-identifying artifact from this run and shouldn't
   linger.

7. **Score the run:**
   ```bash
   <python> -m scripts.score_run <run_id>
   ```
   Write its output to `evals/results/condition-<x>/score-<run_id>.md`.

8. **Promote the structured run log** from `evals/results/runs/<run_id>.json`
   (gitignored scratch space) to `evals/results/condition-<x>/run-<run_id>.json`
   (tracked) — this is the permanent record of what was asked, what SQL ran,
   and what was submitted for this condition run.

9. **Report a one-line summary**: condition, run id, `<pass>/<objective>`
   PASS on Level 1-2 questions, count of `NEEDS_REVIEW` (Level 3-4, needs
   human read against `evals/expected.md`), count of `MISSING` or `ERROR` (a
   non-zero `ERROR`/`MISSING` count means the agent didn't complete the task
   cleanly — investigate before trusting the PASS rate).

## Validation

`/run-eval --condition c` should reproduce Condition C's Phase 1 result
(20/20 PASS on the objective questions, per `evals/results/comparison.md`)
within `scripts/score_run.py`'s tolerance — this is the reproduction check
that confirms the MCP-based mechanism measures the same thing Phase 1's
manual process did, just captured differently (see PRD.md §12's Phase 2
validation criterion).

## Notes

- Level 3-4 (`NEEDS_REVIEW`) questions are never auto-scored — see
  `scripts/score_run.py`'s module docstring for why forcing a fuzzy prose
  comparison against `evals/expected.md` would be dishonest either way
  (too strict or too loose).
- If an agent calls `query_database` with a write/DDL statement, the server
  rejects it (`QueryRejected`) — this is expected and does not indicate a
  bug in the skill.
- Re-running the same `--run-id` twice is refused by design (step 2) so a
  partial or bad run can't silently overwrite good data — pick a new run id
  or delete the stale `evals/results/runs/<run_id>.json` first if you
  intend to redo it.
