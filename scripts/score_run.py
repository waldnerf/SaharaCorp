"""Scores a run captured by the MCP question-server (question_server/) against
the canonical answers in scripts/verify_expected.py.

Supersedes the transcript-regex-parsing scorer originally scoped in
.claude/plans/context-layer-lab-phase2.md (Phase 2e's score_transcript.py):
now that the agent submits SQL through submit_answer as a structured tool
call, there is no free-form markdown to parse. Each submitted answer already
carries its own final SQL, so scoring re-executes *that* SQL read-only and
diffs its result rows against the canonical query's rows, rather than
diffing free text.

Reuses scripts.verify_expected.QUERIES as the single source of canonical
SQL — never hand-copies expected values (the exact mistake that caused
Phase 1's Q7/Q8/Q12 ground-truth bugs, see evals/expected.md).
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from question_server.db import QueryRejected, run_query  # noqa: E402
from question_server.questions import load_questions  # noqa: E402
from question_server.run_log import RUNS_DIR  # noqa: E402
from scripts.verify_expected import QUERIES  # noqa: E402

# Only Level 1-2 questions have a single objective numeric answer that can
# be diffed automatically. Level 3-4 are open-ended prose (see PRD.md and
# the Phase 2 plan's NOTES on why this scorer doesn't force-automate those).
OBJECTIVE_LEVELS = {1, 2}

RELATIVE_TOLERANCE = 0.005  # 0.5%, matching the Phase 2 plan's stated tolerance

_CANONICAL_SQL: dict[int, str] = dict(QUERIES)


@dataclass
class QuestionScore:
    question_id: int
    verdict: str  # PASS | FAIL | NEEDS_REVIEW | MISSING | ERROR
    detail: str
    agent_sql: str | None = None
    agent_rows: list[tuple] | None = None
    canonical_rows: list[tuple] | None = None


@dataclass
class RunScore:
    run_id: str
    scores: list[QuestionScore] = field(default_factory=list)

    @property
    def pass_count(self) -> int:
        return sum(1 for s in self.scores if s.verdict == "PASS")

    @property
    def objective_count(self) -> int:
        return sum(1 for s in self.scores if s.verdict in ("PASS", "FAIL", "ERROR"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "pass_count": self.pass_count,
            "objective_count": self.objective_count,
            "scores": [
                {
                    "question_id": s.question_id,
                    "verdict": s.verdict,
                    "detail": s.detail,
                }
                for s in self.scores
            ],
        }


_NUMERIC_TYPES = (int, float, Decimal)


def _to_comparable_row(row: tuple) -> tuple:
    return tuple(round(v, 4) if isinstance(v, _NUMERIC_TYPES) else v for v in row)


def _rows_match(agent_rows: list[tuple], canonical_rows: list[tuple]) -> tuple[str, str]:
    """Returns (verdict, detail) where verdict is MATCH, MISMATCH, or
    SHAPE_MISMATCH. SHAPE_MISMATCH (different row/column count) means the
    agent's SQL returns data in a different shape than the canonical query —
    that's often a harmless stylistic choice (an extra label column, a
    different but equally valid grouping), not necessarily a wrong answer,
    so it's surfaced for human review rather than auto-failed."""
    if len(agent_rows) != len(canonical_rows):
        return (
            "SHAPE_MISMATCH",
            f"row count mismatch: agent={len(agent_rows)} canonical={len(canonical_rows)} "
            "(cannot safely auto-compare — different shape, not necessarily wrong)",
        )

    if agent_rows and canonical_rows and len(agent_rows[0]) != len(canonical_rows[0]):
        return (
            "SHAPE_MISMATCH",
            f"column count mismatch: agent={len(agent_rows[0])} canonical={len(canonical_rows[0])} "
            "(cannot safely auto-compare — different shape, not necessarily wrong)",
        )

    agent_sorted = sorted(_to_comparable_row(r) for r in agent_rows)
    canonical_sorted = sorted(_to_comparable_row(r) for r in canonical_rows)

    for agent_row, canonical_row in zip(agent_sorted, canonical_sorted):
        for agent_val, canonical_val in zip(agent_row, canonical_row):
            if isinstance(canonical_val, _NUMERIC_TYPES) and isinstance(agent_val, _NUMERIC_TYPES):
                if canonical_val == 0:
                    if abs(agent_val) > 1e-6:
                        return "MISMATCH", f"expected ~0, got {agent_val}"
                elif abs(float(agent_val) - float(canonical_val)) / abs(float(canonical_val)) > RELATIVE_TOLERANCE:
                    return "MISMATCH", f"{agent_val} not within {RELATIVE_TOLERANCE:.1%} of {canonical_val}"
            elif str(agent_val).strip().lower() != str(canonical_val).strip().lower():
                return "MISMATCH", f"{agent_val!r} != {canonical_val!r}"

    return "MATCH", "matches canonical result within tolerance"


def score_run(run_id: str) -> RunScore:
    run_path = RUNS_DIR / f"{run_id}.json"
    if not run_path.exists():
        raise FileNotFoundError(f"No run log at {run_path} — run the MCP server and submit answers first")
    run_data = json.loads(run_path.read_text(encoding="utf-8"))

    answers_by_id = {a["question_id"]: a for a in run_data["answers"]}
    questions = load_questions()

    result = RunScore(run_id=run_id)
    for question in questions:
        answer = answers_by_id.get(question.id)

        if answer is None:
            result.scores.append(
                QuestionScore(question.id, "MISSING", "no submit_answer call recorded for this question")
            )
            continue

        if question.level not in OBJECTIVE_LEVELS:
            result.scores.append(
                QuestionScore(
                    question.id,
                    "NEEDS_REVIEW",
                    f"Level {question.level} ({question.level_name}) is open-ended — needs human/LLM-judge review",
                    agent_sql=answer["sql"],
                )
            )
            continue

        canonical_sql = _CANONICAL_SQL.get(question.id)
        if canonical_sql is None:
            result.scores.append(
                QuestionScore(question.id, "NEEDS_REVIEW", "no canonical SQL defined for this question id")
            )
            continue

        try:
            agent_rows = [tuple(row.values()) for row in run_query(answer["sql"])]
        except QueryRejected as exc:
            result.scores.append(QuestionScore(question.id, "ERROR", f"agent SQL rejected: {exc}", agent_sql=answer["sql"]))
            continue
        except Exception as exc:  # DuckDB syntax/execution errors
            result.scores.append(QuestionScore(question.id, "ERROR", f"agent SQL failed: {exc}", agent_sql=answer["sql"]))
            continue

        canonical_rows = [tuple(row.values()) for row in run_query(canonical_sql)]

        verdict, detail = _rows_match(agent_rows, canonical_rows)
        display_verdict = {"MATCH": "PASS", "MISMATCH": "FAIL", "SHAPE_MISMATCH": "NEEDS_REVIEW"}[verdict]
        result.scores.append(
            QuestionScore(
                question.id,
                display_verdict,
                detail,
                agent_sql=answer["sql"],
                agent_rows=agent_rows,
                canonical_rows=canonical_rows,
            )
        )

    return result


def format_report(score: RunScore) -> str:
    lines = [f"# Score: run `{score.run_id}`", ""]
    lines.append(f"Objective questions (Level 1-2): {score.pass_count}/{score.objective_count} PASS")
    lines.append("")
    lines.append("| Question | Verdict | Detail |")
    lines.append("|---|---|---|")
    for s in score.scores:
        lines.append(f"| Q{s.question_id} | {s.verdict} | {s.detail} |")
    return "\n".join(lines)


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python -m scripts.score_run <run_id>", file=sys.stderr)
        sys.exit(1)
    score = score_run(sys.argv[1])
    print(format_report(score))


if __name__ == "__main__":
    main()
