"""Per-run state: every query_database call and submit_answer call is
appended here, then persisted to evals/results/runs/<run_id>.json so
export_run (and a crash-recovery read) can reconstruct the full run
without depending on the server process staying alive.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = REPO_ROOT / "evals" / "results" / "runs"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RunLog:
    run_id: str
    condition_letter: str  # kept in the on-disk log for scoring; never returned to the agent
    queries: list[dict[str, Any]] = field(default_factory=list)
    answers: dict[int, dict[str, Any]] = field(default_factory=dict)
    started_at: str = field(default_factory=_now)

    def record_query(self, question_id: int | None, sql: str, row_count: int) -> None:
        self.queries.append(
            {
                "question_id": question_id,
                "sql": sql,
                "row_count": row_count,
                "at": _now(),
            }
        )
        self._save()

    def record_answer(self, question_id: int, sql: str, answer: str) -> None:
        self.answers[question_id] = {
            "question_id": question_id,
            "sql": sql,
            "answer": answer,
            "at": _now(),
        }
        self._save()

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "condition": self.condition_letter,
            "started_at": self.started_at,
            "queries": self.queries,
            "answers": [self.answers[qid] for qid in sorted(self.answers)],
        }

    def _save(self) -> None:
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        path = RUNS_DIR / f"{self.run_id}.json"
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")


def load_run(run_id: str) -> dict[str, Any] | None:
    path = RUNS_DIR / f"{run_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
