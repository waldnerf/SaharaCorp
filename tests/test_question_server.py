"""Verifies the MCP question-server's condition isolation: each of the 5
conditions (A-E) must expose exactly the context files evals/conditions.yaml
says it should, no tool/description/error may leak the condition letter,
query_database must stay read-only, and export_run must round-trip a
submitted answer without leaking the condition.
"""
import asyncio

import pytest

from question_server.conditions import load_conditions
from question_server.db import QueryRejected, run_query
from question_server.run_log import RUNS_DIR
from question_server.server import build_server


@pytest.fixture(autouse=True)
def _cleanup_run_logs():
    yield
    for path in RUNS_DIR.glob("test-*.json"):
        path.unlink()


def _call(server, tool_name, args=None):
    """Unwraps a tool's structured_content. List/scalar returns come back
    wrapped as {"result": ...}; dict returns come back as the dict itself."""
    result = asyncio.run(server.call_tool(tool_name, args or {}))
    content = result.structured_content
    if content is not None and set(content.keys()) == {"result"}:
        return content["result"]
    return content


@pytest.mark.parametrize("letter", ["A", "B", "C", "D", "E"])
def test_context_bundle_matches_conditions_yaml(letter):
    conditions = load_conditions()
    expected_files = set(conditions[letter].context_files)

    server = build_server(letter, run_id=f"test-{letter}")
    bundle = _call(server, "get_context_bundle")

    assert set(bundle.keys()) == expected_files
    for path in expected_files:
        assert bundle[path], f"{path} was empty for condition {letter}"


def test_conditions_are_strictly_nested_by_design():
    """A ⊂ B, A ⊂ C ⊂ D ⊂ E, B ⊂ E — catches an editing mistake in
    conditions.yaml where a later condition drops a file an earlier one had."""
    conditions = load_conditions()
    a, b, c, d, e = (set(conditions[x].context_files) for x in "ABCDE")
    assert a == set()
    assert a <= b
    assert a <= c <= d <= e
    assert b <= e


@pytest.mark.parametrize("letter", ["A", "B", "C", "D", "E"])
def test_tool_surface_is_condition_invariant(letter):
    """The set of exposed tools and their descriptions must be identical
    across conditions — only get_context_bundle's *contents* may vary."""
    server = build_server(letter, run_id=f"test-tools-{letter}")
    tools = asyncio.run(server.list_tools())
    names = sorted(t.name for t in tools)
    assert names == [
        "export_run",
        "get_context_bundle",
        "get_question",
        "get_schema",
        "list_questions",
        "query_database",
        "submit_answer",
    ]
    for tool in tools:
        assert tool.description is not None
        assert "condition" not in tool.description.lower()
        for letter_check in "ABCDE":
            assert f" {letter_check} " not in f" {tool.description} "


def test_schema_is_condition_invariant():
    schema_a = _call(build_server("A", run_id="test-schema-a"), "get_schema")
    schema_e = _call(build_server("E", run_id="test-schema-e"), "get_schema")
    assert schema_a == schema_e
    assert len(schema_a) > 0


def test_query_database_rejects_writes():
    with pytest.raises(QueryRejected):
        run_query("DELETE FROM orders")
    with pytest.raises(QueryRejected):
        run_query("DROP TABLE orders")
    rows = run_query("SELECT COUNT(*) AS n FROM orders")
    assert rows[0]["n"] > 0


def test_submit_answer_and_export_run_round_trip_without_leaking_condition():
    server = build_server("D", run_id="test-export-roundtrip")

    _call(server, "query_database", {"sql": "SELECT 1 AS x", "question_id": 1})
    _call(server, "submit_answer", {"question_id": 1, "sql": "SELECT 1 AS x", "answer": "1"})

    exported = _call(server, "export_run", {"run_id": "test-export-roundtrip"})
    assert "condition" not in exported
    assert exported["answers"][0] == {
        "question_id": 1,
        "sql": "SELECT 1 AS x",
        "answer": "1",
    } | {"at": exported["answers"][0]["at"]}
    assert len(exported["queries"]) == 1


def test_export_run_rejects_mismatched_run_id():
    from mcp.server.mcpserver.exceptions import ToolError

    server = build_server("C", run_id="test-run-real")
    with pytest.raises(ToolError):
        asyncio.run(server.call_tool("export_run", {"run_id": "someone-elses-run"}))
