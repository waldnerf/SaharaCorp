"""Scores a wording-variant run (evals/questions_wording_variants.md,
ids 101-106 mapping to V1-V6) the same way scripts.score_run scores the
main 20 — re-executing the agent's submitted SQL and diffing against the
canonical query for whichever original question (Q1/Q2/Q7) the variant
pairs with, via scripts.verify_expected_wording_variants.VARIANT_PAIRING.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from question_server.db import QueryRejected, run_query  # noqa: E402
from question_server.run_log import RUNS_DIR  # noqa: E402
from scripts.score_run import _rows_match  # noqa: E402
from scripts.verify_expected import QUERIES  # noqa: E402
from scripts.verify_expected_wording_variants import VARIANT_PAIRING  # noqa: E402

_CANONICAL_SQL = dict(QUERIES)
# ids 101-106 -> V1-V6, matching evals/questions_wording_variants.md's ordering
_VARIANT_ID_TO_LABEL = {101 + i: label for i, label in enumerate(VARIANT_PAIRING)}


def score_variant_run(run_id: str) -> list[dict]:
    run_path = RUNS_DIR / f"{run_id}.json"
    if not run_path.exists():
        raise FileNotFoundError(f"No run log at {run_path}")
    run_data = json.loads(run_path.read_text(encoding="utf-8"))
    answers_by_id = {a["question_id"]: a for a in run_data["answers"]}

    results = []
    for question_id, label in _VARIANT_ID_TO_LABEL.items():
        original_qid = VARIANT_PAIRING[label]
        canonical_sql = _CANONICAL_SQL[original_qid]
        answer = answers_by_id.get(question_id)

        if answer is None:
            results.append({"id": question_id, "label": label, "verdict": "MISSING", "detail": ""})
            continue

        try:
            agent_rows = [tuple(row.values()) for row in run_query(answer["sql"])]
        except QueryRejected as exc:
            results.append({"id": question_id, "label": label, "verdict": "ERROR", "detail": str(exc)})
            continue
        except Exception as exc:
            results.append({"id": question_id, "label": label, "verdict": "ERROR", "detail": str(exc)})
            continue

        canonical_rows = [tuple(row.values()) for row in run_query(canonical_sql)]
        verdict, detail = _rows_match(agent_rows, canonical_rows)
        display = {"MATCH": "PASS", "MISMATCH": "FAIL", "SHAPE_MISMATCH": "NEEDS_REVIEW"}[verdict]
        results.append({"id": question_id, "label": label, "verdict": display, "detail": detail})

    return results


def main() -> None:
    run_id = sys.argv[1]
    for r in score_variant_run(run_id):
        print(f"{r['label']} (id {r['id']}): {r['verdict']} — {r['detail']}")


if __name__ == "__main__":
    main()
