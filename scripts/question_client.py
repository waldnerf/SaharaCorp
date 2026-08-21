"""One-shot CLI wrapper around question_server's internals, for driving a
condition run via ordinary Bash calls instead of a live MCP stdio session.

Why this exists: the real MCP server (question_server/__main__.py) holds a
JSON-RPC session open over stdin/stdout. That's fine for a client that
speaks MCP natively, but a subagent issuing separate, one-shot Bash tool
calls can't hold a persistent pipe open across calls. This module exposes
the exact same condition-scoped functions server.py wraps as MCP tools
(resolve_condition, load_context_bundle, load_questions, run_query,
RunLog), as plain CLI subcommands that each read/write the same on-disk
run log — so a run driven through this client is scored identically to one
driven through the real server, by the same scripts/score_run.py.

Every subcommand requires --condition and --run-id explicitly; nothing
here infers or hides the condition from its caller, since this tool is
meant to be run by an operator/harness-level process, not by the agent
under test itself (contrast with question_server/server.py, where the
condition is deliberately invisible to the connected agent).
"""
from __future__ import annotations

import argparse
import json
import sys

from question_server.conditions import load_context_bundle, resolve_condition
from question_server.db import QueryRejected, get_schema, run_query
from question_server.questions import get_question, load_questions
from question_server.run_log import RunLog


def cmd_list_questions(args: argparse.Namespace) -> None:
    questions = load_questions()
    if args.level is not None:
        questions = [q for q in questions if q.level == args.level]
    print(json.dumps([{"id": q.id, "text": q.text} for q in questions], indent=2))


def cmd_get_question(args: argparse.Namespace) -> None:
    q = get_question(args.question_id)
    if q is None:
        sys.exit(f"No question with id {args.question_id}")
    print(json.dumps({"id": q.id, "text": q.text}, indent=2))


def cmd_get_schema(args: argparse.Namespace) -> None:
    print(json.dumps(get_schema(), indent=2))


def cmd_get_context_bundle(args: argparse.Namespace) -> None:
    condition = resolve_condition(args.condition)
    print(json.dumps(load_context_bundle(condition), indent=2))


def cmd_query(args: argparse.Namespace) -> None:
    try:
        rows = run_query(args.sql)
    except QueryRejected as exc:
        sys.exit(str(exc))
    run_log = RunLog.load_or_create(args.run_id, args.condition)
    run_log.record_query(args.question_id, args.sql, len(rows))
    print(json.dumps(rows, indent=2, default=str))


def cmd_submit_answer(args: argparse.Namespace) -> None:
    run_log = RunLog.load_or_create(args.run_id, args.condition)
    run_log.record_answer(args.question_id, args.sql, args.answer)
    print(json.dumps({"question_id": args.question_id, "recorded": True}))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="question_client")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_run_scoped(p: argparse.ArgumentParser) -> None:
        p.add_argument("--condition", required=True, choices=["A", "B", "C", "D", "E"])
        p.add_argument("--run-id", required=True)

    # Condition-invariant, unlogged — no --condition/--run-id needed.
    p = sub.add_parser("list-questions")
    p.add_argument("--level", type=int, default=None)
    p.set_defaults(func=cmd_list_questions)

    p = sub.add_parser("get-question")
    p.add_argument("question_id", type=int)
    p.set_defaults(func=cmd_get_question)

    p = sub.add_parser("get-schema")
    p.set_defaults(func=cmd_get_schema)

    # Run-scoped — these need to know which condition/run they belong to.
    p = sub.add_parser("get-context-bundle")
    add_run_scoped(p)
    p.set_defaults(func=cmd_get_context_bundle)

    p = sub.add_parser("query")
    p.add_argument("sql")
    p.add_argument("--question-id", type=int, default=None)
    add_run_scoped(p)
    p.set_defaults(func=cmd_query)

    p = sub.add_parser("submit-answer")
    p.add_argument("question_id", type=int)
    p.add_argument("sql")
    p.add_argument("answer")
    add_run_scoped(p)
    p.set_defaults(func=cmd_submit_answer)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
