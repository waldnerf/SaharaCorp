"""Entry point: python -m question_server --condition C --run-id run001

Launches one MCP server instance scoped to a single condition and run,
over stdio, matching how /run-eval spawns a fresh agent against a fresh
server per condition (see PRD.md §7/§12).
"""
from __future__ import annotations

import argparse
import uuid

from question_server.server import build_server


def main() -> None:
    parser = argparse.ArgumentParser(prog="question_server")
    parser.add_argument(
        "--condition",
        required=True,
        choices=["A", "B", "C", "D", "E"],
        help="Condition letter to run under (operator-only flag; never exposed to the agent).",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Identifier for this run, used for the exported run log. Defaults to a fresh UUID.",
    )
    args = parser.parse_args()

    run_id = args.run_id or uuid.uuid4().hex[:12]
    server = build_server(args.condition, run_id)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
