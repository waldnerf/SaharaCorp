"""Runs the ground-truth SQL for evals/questions_wording_variants.md.

Reuses scripts.verify_expected's QUERIES rather than re-deriving values by
hand — every variant's correct answer is identical to its paired original
question's answer (the governed convention is always net-of-returns; only
the *wording* changes between variants, never the correct computation). See
that module's docstring for the same never-hand-type-expected-answers rule.
"""
from pathlib import Path

import duckdb

from scripts.verify_expected import QUERIES

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "retail.duckdb"

# variant_id -> original question_id whose canonical SQL/result applies unchanged
VARIANT_PAIRING = {
    "V1": 1,  # explicit, pairs with Q1
    "V2": 1,  # ambiguous control, pairs with Q1
    "V3": 2,  # explicit, pairs with Q2
    "V4": 2,  # ambiguous control, pairs with Q2
    "V5": 7,  # explicit, pairs with Q7
    "V6": 7,  # ambiguous control, pairs with Q7
}

_QUERIES_BY_ID = dict(QUERIES)


def main() -> None:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        for variant_id, original_qid in VARIANT_PAIRING.items():
            sql = _QUERIES_BY_ID[original_qid]
            result = con.sql(sql).fetchall()
            print(f"=== {variant_id} (pairs with Q{original_qid}) ===")
            print(sql.strip())
            print("--- result ---")
            for row in result:
                print(row)
            print()
    finally:
        con.close()


if __name__ == "__main__":
    main()
