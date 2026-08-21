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


def build_html(data: dict) -> None:
    """Injects comparison.json into docs/comparison.html.template, producing
    docs/comparison.html — the single interactive file, self-contained (JSON
    embedded inline) so it opens directly via file:// with no build step or
    local server required."""
    template_path = REPO_ROOT / "docs" / "comparison.html.template"
    out_path = REPO_ROOT / "docs" / "comparison.html"
    template = template_path.read_text(encoding="utf-8")
    # Defense in depth: the HTML parser ends a <script> block on any literal
    # "</script" regardless of the script's type, even inside a JSON payload.
    json_text = json.dumps(data).replace("</script", "<\\/script")
    html = template.replace("__COMPARISON_DATA__", json_text)
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

    build_html(data)


if __name__ == "__main__":
    main()
