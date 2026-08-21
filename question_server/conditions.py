"""Loads evals/conditions.yaml and resolves a condition letter to the exact
context files a server instance is allowed to expose.

This is the single point where "which condition is active" exists as a
concept. Everything downstream of resolve_condition() only ever sees the
resolved file list/content, never the condition letter itself, so the tool
surface can't leak which condition (A-E) is running.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CONDITIONS_PATH = REPO_ROOT / "evals" / "conditions.yaml"


@dataclass(frozen=True)
class Condition:
    letter: str
    label: str
    description: str
    schema_only: bool
    context_files: tuple[str, ...]


def load_conditions() -> dict[str, Condition]:
    raw = yaml.safe_load(CONDITIONS_PATH.read_text(encoding="utf-8"))
    conditions: dict[str, Condition] = {}
    for letter, cfg in raw["conditions"].items():
        conditions[letter] = Condition(
            letter=letter,
            label=cfg["label"],
            description=cfg["description"],
            schema_only=cfg.get("schema_only", True),
            context_files=tuple(cfg.get("context_files", [])),
        )
    return conditions


def resolve_condition(letter: str) -> Condition:
    conditions = load_conditions()
    if letter not in conditions:
        valid = ", ".join(sorted(conditions))
        raise ValueError(f"Unknown condition {letter!r}. Valid conditions: {valid}")
    return conditions[letter]


def load_context_bundle(condition: Condition) -> dict[str, str]:
    """Reads every file listed for this condition and returns {path: content}.

    Paths are relative to the repo root, matching what a human running the
    Phase 1 worktree process would have seen for the same condition.
    """
    bundle: dict[str, str] = {}
    for rel_path in condition.context_files:
        full_path = REPO_ROOT / rel_path
        bundle[rel_path] = full_path.read_text(encoding="utf-8")
    return bundle
