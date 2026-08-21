"""Verifies scripts/score_run.py's PASS/FAIL/NEEDS_REVIEW/MISSING classification
against synthetic runs, and its own correctness check: scoring Condition C's
Phase 1 SQL (transcribed from evals/results/condition-c) against the canonical
answers must come back all PASS on the objective questions, matching
comparison.md's manually-scored result.
"""
import asyncio

import pytest

from question_server.run_log import RUNS_DIR
from question_server.server import build_server
from scripts.score_run import score_run

Q1_CORRECT_SQL = (
    "SELECT o.country, "
    "ROUND(SUM((oi.quantity - COALESCE(r.quantity_returned,0)) * oi.unit_price "
    "* (1-oi.line_discount_pct) * o.fx_rate_to_eur),2) AS revenue_eur "
    "FROM order_items oi JOIN orders o ON o.order_id=oi.order_id "
    "LEFT JOIN returns r ON r.order_item_id=oi.order_item_id "
    "WHERE o.status='completed' GROUP BY 1 ORDER BY 1"
)


@pytest.fixture(autouse=True)
def _cleanup_run_logs():
    yield
    for path in RUNS_DIR.glob("test-score-*.json"):
        path.unlink()


def _submit(server, question_id, sql, answer="n/a"):
    asyncio.run(
        server.call_tool(
            "submit_answer", {"question_id": question_id, "sql": sql, "answer": answer}
        )
    )


def test_correct_sql_scores_pass():
    server = build_server("C", run_id="test-score-pass")
    _submit(server, 1, Q1_CORRECT_SQL)

    result = score_run("test-score-pass")
    q1 = next(s for s in result.scores if s.question_id == 1)
    assert q1.verdict == "PASS"


def test_wrong_sql_scores_fail():
    server = build_server("C", run_id="test-score-fail")
    _submit(server, 4, "SELECT COUNT(*) FROM shipments")  # ignores the Belgium filter

    result = score_run("test-score-fail")
    q4 = next(s for s in result.scores if s.question_id == 4)
    assert q4.verdict == "FAIL"


def test_invalid_sql_scores_error():
    server = build_server("C", run_id="test-score-error")
    _submit(server, 1, "SELECT this is not valid sql")

    result = score_run("test-score-error")
    q1 = next(s for s in result.scores if s.question_id == 1)
    assert q1.verdict == "ERROR"


def test_write_attempt_scores_error_not_silently_accepted():
    server = build_server("C", run_id="test-score-write")
    _submit(server, 1, "DELETE FROM orders")

    result = score_run("test-score-write")
    q1 = next(s for s in result.scores if s.question_id == 1)
    assert q1.verdict == "ERROR"


def test_level_3_question_is_needs_review_not_scored():
    server = build_server("C", run_id="test-score-review")
    _submit(server, 11, "SELECT 1", answer="yes, there is margin headroom")

    result = score_run("test-score-review")
    q11 = next(s for s in result.scores if s.question_id == 11)
    assert q11.verdict == "NEEDS_REVIEW"


def test_unanswered_question_is_missing():
    server = build_server("C", run_id="test-score-missing")
    _submit(server, 1, Q1_CORRECT_SQL)

    result = score_run("test-score-missing")
    q2 = next(s for s in result.scores if s.question_id == 2)
    assert q2.verdict == "MISSING"


def test_missing_run_log_raises():
    with pytest.raises(FileNotFoundError):
        score_run("no-such-run-id-ever")
