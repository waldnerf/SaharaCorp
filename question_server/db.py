"""Read-only DuckDB access for query_database.

DuckDB's own read_only=True connection mode is the real guard — it refuses
any statement that would write to the database file, regardless of what
the SQL text looks like. The keyword denylist below is defense-in-depth
only, to fail fast with a clear message before DuckDB even gets to run
the statement.
"""
from __future__ import annotations

import re
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "data" / "retail.duckdb"

_WRITE_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|COPY|EXPORT|IMPORT|PRAGMA|SET|CALL|VACUUM)\b",
    re.IGNORECASE,
)


class QueryRejected(Exception):
    pass


def run_query(sql: str) -> list[dict]:
    if _WRITE_KEYWORDS.search(sql):
        raise QueryRejected(
            "This tool is read-only. The query contains a keyword that is "
            "not permitted (data-modifying, DDL, or session-control statements)."
        )

    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        result = con.sql(sql)
        columns = result.columns
        rows = result.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    finally:
        con.close()


def get_schema() -> list[dict]:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        rows = con.sql(
            """
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'main'
            ORDER BY table_name, ordinal_position
            """
        ).fetchall()
        return [
            {"table": table, "column": column, "type": dtype}
            for table, column, dtype in rows
        ]
    finally:
        con.close()
