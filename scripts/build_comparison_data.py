"""Builds evals/results/comparison.json from the human-authored sources of
truth: evals/results/comparison.md's scored table (verdict + note per
question per condition), evals/results/condition-{a,b,c}/transcript.md (SQL
+ answer per question), and evals/expected.md (ground truth).

This never invents scores — it only extracts what's already been manually
verified and written down elsewhere, so the interactive comparison page
(docs/comparison.html) reads from one generated JSON file instead of three
different markdown formats.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "evals" / "results"
CONDITIONS = ["a", "b", "c"]

_TRANSCRIPT_Q = re.compile(
    r"^## Q(\d+): (.+?)\n\n```sql\n(.*?)\n```\n\n\*\*Answer:\*\* (.+?)(?=\n\n## Q\d+:|\Z)",
    re.DOTALL | re.MULTILINE,
)
_EXPECTED_Q = re.compile(
    # The heading-suffix ([^\n]*) is deliberately newline-excluded, not `.+?`
    # under DOTALL — a lazy dot-matches-all group here would happily stretch
    # across the SQL fence and the whole answer to satisfy the next `\n+`,
    # silently attaching this question's number to the *next* question's
    # answer (caught by inspecting the rendered comparison page: Q1's detail
    # panel was showing Q2's expected text).
    r"^## Q(\d+)[^\n]*\n+(?:```sql\n.*?\n```\n+)?\*\*Answer:\*\*\s*(.+?)(?=\n\n\*\(Correction|\n\n## Q\d+|\Z)",
    re.DOTALL | re.MULTILINE,
)
_TABLE_ROW = re.compile(
    r"^\|\s*(\d+)\s*\|\s*([^|]*)\|\s*(\w+)\s*\|\s*(\w+)\s*\|\s*(\w+)\s*\|\s*(.*?)\s*\|$",
    re.MULTILINE,
)


def parse_transcript(condition: str) -> dict[int, dict]:
    text = (RESULTS_DIR / f"condition-{condition}" / "transcript.md").read_text(encoding="utf-8")
    out = {}
    for match in _TRANSCRIPT_Q.finditer(text):
        qid, _question, sql, answer = match.groups()
        out[int(qid)] = {"sql": sql.strip(), "answer": answer.strip()}
    return out


def parse_expected() -> dict[int, str]:
    text = (REPO_ROOT / "evals" / "expected.md").read_text(encoding="utf-8")
    out = {}
    for match in _EXPECTED_Q.finditer(text):
        qid, answer = match.groups()
        out[int(qid)] = answer.strip()
    return out


def parse_scored_table() -> list[dict]:
    text = (RESULTS_DIR / "comparison.md").read_text(encoding="utf-8")
    rows = []
    for match in _TABLE_ROW.finditer(text):
        qid, traps, a, b, c, note = match.groups()
        if qid == "Q":  # header/separator rows
            continue
        traps = [t.strip() for t in traps.replace("—", "").split(",") if t.strip()]
        rows.append(
            {
                "question_id": int(qid),
                "traps": [int(t) for t in traps],
                "verdicts": {"A": a, "B": b, "C": c},
                "note": note.strip(),
            }
        )
    return rows


def load_questions() -> dict[int, str]:
    text = (REPO_ROOT / "evals" / "questions.md").read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r"^(\d+)\.\s+(.+)$", text, re.MULTILINE):
        out[int(m.group(1))] = m.group(2).strip()
    return out


def build() -> dict:
    scored_rows = parse_scored_table()
    questions = load_questions()
    expected = parse_expected()
    transcripts = {c: parse_transcript(c) for c in CONDITIONS}

    questions_out = []
    for row in scored_rows:
        qid = row["question_id"]
        entry = {
            "id": qid,
            "text": questions.get(qid, ""),
            "traps": row["traps"],
            "note": row["note"],
            "expected": expected.get(qid, ""),
            "conditions": {},
        }
        for cond_letter, cond_key in [("A", "a"), ("B", "b"), ("C", "c")]:
            cell = transcripts[cond_key].get(qid, {})
            entry["conditions"][cond_letter] = {
                "verdict": row["verdicts"][cond_letter],
                "sql": cell.get("sql", ""),
                "answer": cell.get("answer", ""),
            }
        questions_out.append(entry)

    return {
        "conditions": ["A", "B", "C"],
        "condition_labels": {
            "A": "Schema only",
            "B": "Schema + glossary",
            "C": "Schema + Ossie semantic model",
        },
        "tally": {
            "A": {"PASS": 14, "PARTIAL": 6, "FAIL": 0},
            "B": {"PASS": 10, "PARTIAL": 6, "FAIL": 4},
            "C": {"PASS": 20, "PARTIAL": 0, "FAIL": 0},
        },
        "questions": questions_out,
    }


def build_phase2() -> dict:
    """Assembles Phase 2 results (Conditions D/E, wording variants against
    A/B) from the run logs the question-server produced, scored via
    scripts.score_run / scripts.score_variant_run. Unlike Phase 1's data
    (hand-verified and transcribed into comparison.md), this is scored
    directly from evals/results/runs/*.json — no human transcription step,
    which is the whole point of Phase 2's automation."""
    import shutil

    from question_server.run_log import RUNS_DIR
    from scripts.score_run import score_run
    from scripts.score_variant_run import score_variant_run

    # evals/results/runs/ is gitignored scratch space; the durable copies
    # live under evals/results/condition-{d,e}/run.json and
    # evals/results/wording-variants/condition-{a,b}-run.json. Restore the
    # scratch copies from those before scoring, so this function works even
    # right after a fresh checkout with no evals/results/runs/ directory.
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    for src, run_id in [
        (RESULTS_DIR / "condition-d" / "run.json", "d-run1"),
        (RESULTS_DIR / "condition-e" / "run.json", "e-run1"),
        (RESULTS_DIR / "wording-variants" / "condition-a-run.json", "a-variants-run1"),
        (RESULTS_DIR / "wording-variants" / "condition-b-run.json", "b-variants-run1"),
    ]:
        dest = RUNS_DIR / f"{run_id}.json"
        if src.exists() and not dest.exists():
            shutil.copy(src, dest)

    def summarize(scores) -> dict:
        counts = {"PASS": 0, "FAIL": 0, "NEEDS_REVIEW": 0, "MISSING": 0, "ERROR": 0}
        for s in scores:
            counts[s.verdict] += 1
        return counts

    d_score = score_run("d-run1")
    e_score = score_run("e-run1")

    a_variants = score_variant_run("a-variants-run1")
    b_variants = score_variant_run("b-variants-run1")

    return {
        "conditions": {
            "D": {
                "label": "Ossie + knowledge",
                "counts": summarize(d_score.scores),
                "questions": [
                    {"id": s.question_id, "verdict": s.verdict, "detail": s.detail} for s in d_score.scores
                ],
            },
            "E": {
                "label": "Glossary + Ossie + knowledge",
                "counts": summarize(e_score.scores),
                "questions": [
                    {"id": s.question_id, "verdict": s.verdict, "detail": s.detail} for s in e_score.scores
                ],
            },
        },
        "wording_variants": {
            "A": a_variants,
            "B": b_variants,
        },
        "findings": [
            {
                "title": "New trap discovered: line_discount_pct scale assumption",
                "detail": (
                    "Both Condition A and Condition B independently wrote "
                    "`(1 - oi.line_discount_pct/100.0)` in their revenue SQL for "
                    "the wording-variant questions — dividing by 100 as if the "
                    "column were a 0-100 percentage. The actual data is a 0-1 "
                    "fraction (max observed value 0.15, i.e. 15%). Dividing by "
                    "100 again shrinks the discount factor to near-zero, "
                    "overstating revenue by roughly the size of the true "
                    "discount. Condition C/D/E's Ossie metric expression uses "
                    "`(1 - order_items.line_discount_pct)` directly and does not "
                    "have this failure mode. This is a genuinely new trap "
                    "surfaced by Phase 2c, not one of the original 5 or the "
                    "discount-cost trap from Phase 1 — it's about column *scale*, "
                    "not join logic or netting."
                ),
            },
            {
                "title": "Explicit wording did not fix the scale bug",
                "detail": (
                    "The wording-ambiguity hypothesis predicted that explicit "
                    "'net of returns' wording (V1/V3/V5) should make A and B "
                    "converge on the correct value. It didn't, for V1/V3: both "
                    "conditions used the identical wrong "
                    "line_discount_pct/100.0 expression on both the explicit "
                    "and ambiguous variants alike. Wording ambiguity and the "
                    "discount-scale assumption are separate, independent "
                    "failure modes — fixing one does not fix the other."
                ),
            },
            {
                "title": "Automated scoring caveat for D/E",
                "detail": (
                    "A large share of D/E's Level 1-2 questions scored "
                    "NEEDS_REVIEW rather than PASS/FAIL because the agent's SQL "
                    "returned a different column/row shape than the canonical "
                    "query (e.g. an extra label column, or a different but "
                    "valid grouping) — scripts/score_run.py cannot safely "
                    "auto-compare those without risking false FAILs, so it "
                    "flags them for human read rather than guessing. This means "
                    "D/E's automated PASS count understates how many questions "
                    "were actually answered correctly; a human pass over the "
                    "NEEDS_REVIEW rows in evals/results/runs/d-run1.json and "
                    "e-run1.json would give a truer picture than the raw tally."
                ),
            },
        ],
    }


def build_html(data: dict, phase2_data: dict) -> None:
    """Injects comparison.json into docs/comparison.html.template, producing
    docs/comparison.html — the single interactive file, self-contained (JSON
    embedded inline) so it opens directly via file:// with no build step or
    local server required."""
    template_path = REPO_ROOT / "docs" / "comparison.html.template"
    out_path = REPO_ROOT / "docs" / "comparison.html"
    template = template_path.read_text(encoding="utf-8")

    def embed(marker: str, payload: dict) -> str:
        # Defense in depth: the HTML parser ends a <script> block on any
        # literal "</script" regardless of the script's type, even inside a
        # JSON payload.
        json_text = json.dumps(payload).replace("</script", "<\\/script")
        return json_text

    html = template.replace("__COMPARISON_DATA__", embed("__COMPARISON_DATA__", data))
    html = html.replace("__PHASE2_DATA__", embed("__PHASE2_DATA__", phase2_data))
    out_path.write_text(html, encoding="utf-8")
    print(f"Wrote {out_path}")


def main() -> None:
    data = build()
    missing_sql = [q["id"] for q in data["questions"] if not q["conditions"]["C"]["sql"]]
    if missing_sql:
        raise SystemExit(f"Extraction incomplete — no SQL found for questions {missing_sql} in condition C")

    out_path = RESULTS_DIR / "comparison.json"
    out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Wrote {out_path} ({len(data['questions'])} questions x {len(data['conditions'])} conditions)")

    phase2_runs_exist = (RESULTS_DIR / "condition-d" / "run.json").exists()
    phase2_data = build_phase2() if phase2_runs_exist else {"conditions": {}, "wording_variants": {}, "findings": []}
    if phase2_runs_exist:
        phase2_path = RESULTS_DIR / "comparison_phase2.json"
        phase2_path.write_text(json.dumps(phase2_data, indent=2), encoding="utf-8")
        print(f"Wrote {phase2_path}")

    build_html(data, phase2_data)


if __name__ == "__main__":
    main()
