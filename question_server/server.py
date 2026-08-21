"""Builds an MCPServer instance scoped to one condition and one run.

Design constraint (see PRD.md §10): the tool list and get_context_bundle()'s
contents are the *only* condition signal a server instance carries. No tool
name, description, or error message may mention a condition letter. This
module is the only place that reads the condition letter at all — every
tool closure below only sees the resolved context bundle / schema_only
flag, never the letter itself.
"""
from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from question_server import db, questions
from question_server.conditions import load_context_bundle, resolve_condition
from question_server.run_log import RunLog, load_run


def build_server(condition_letter: str, run_id: str) -> MCPServer:
    condition = resolve_condition(condition_letter)
    context_bundle = load_context_bundle(condition)
    run_log = RunLog.load_or_create(run_id, condition_letter)

    server = MCPServer(
        name="ossie-lab-question-server",
        instructions=(
            "Answer the questions in evals/questions.md using the available "
            "data. Use list_questions to see the question set, get_schema "
            "and get_context_bundle to understand the data, query_database "
            "to run read-only SQL, and submit_answer to record each answer."
        ),
    )

    @server.tool()
    def list_questions(level: int | None = None) -> list[dict[str, Any]]:
        """List eval questions, optionally filtered to one level (1-4)."""
        all_questions = questions.load_questions()
        if level is not None:
            all_questions = [q for q in all_questions if q.level == level]
        return [{"id": q.id, "text": q.text} for q in all_questions]

    @server.tool()
    def get_question(question_id: int) -> dict[str, Any]:
        """Get a single question's text by id."""
        q = questions.get_question(question_id)
        if q is None:
            raise ValueError(f"No question with id {question_id}")
        return {"id": q.id, "text": q.text}

    @server.tool()
    def get_schema() -> list[dict[str, Any]]:
        """List every table and column available in the database, with types."""
        return db.get_schema()

    @server.tool()
    def get_context_bundle() -> dict[str, str]:
        """Get the business/semantic context available for this task, keyed
        by file path. May be empty if no additional context is provided
        beyond the raw schema."""
        return dict(context_bundle)

    @server.tool()
    def query_database(sql: str, question_id: int | None = None) -> list[dict[str, Any]]:
        """Run a read-only SQL query against the database and return rows.
        Pass question_id when this query is being run to answer a specific
        question, so the run log can attribute it correctly."""
        rows = db.run_query(sql)
        run_log.record_query(question_id, sql, len(rows))
        return rows

    @server.tool()
    def submit_answer(question_id: int, sql: str, answer: str) -> dict[str, Any]:
        """Record the final SQL and answer for a question."""
        run_log.record_answer(question_id, sql, answer)
        return {"question_id": question_id, "recorded": True}

    @server.tool()
    def export_run(run_id: str) -> dict[str, Any]:
        """Operator tool: export the full structured record (queries and
        submitted answers) for a run, for scoring. Only returns data for
        the run this server instance is running (run_id must match)."""
        if run_id != run_log.run_id:
            raise ValueError(
                "run_id does not match this server instance's active run."
            )
        record = run_log.to_dict()
        # Condition letter is stripped here — it stays on disk (read by
        # export_run_from_disk for out-of-band scoring) but must never be
        # visible through a tool call, per the condition-isolation design
        # constraint.
        record.pop("condition", None)
        return record

    return server


def export_run_from_disk(run_id: str) -> dict | None:
    """Used by scoring tooling after the server process has exited —
    reads the persisted run log directly rather than going through a tool
    call. Includes the condition letter, unlike export_run's return value
    when called live, since scoring happens out-of-band from the agent."""
    return load_run(run_id)
