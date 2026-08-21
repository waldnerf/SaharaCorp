"""Parses evals/questions.md into structured question records.

Deliberately ignores the "Trap coverage map" table — that section is
scoring metadata, not part of the agent-visible task, and must never be
exposed through list_questions/get_question.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
QUESTIONS_PATH = REPO_ROOT / "evals" / "questions.md"

_LEVEL_HEADING = re.compile(r"^##\s+Level\s+(\d+)\s+—\s+(.+)$")
_QUESTION_LINE = re.compile(r"^(\d+)\.\s+(.+)$")


@dataclass(frozen=True)
class Question:
    id: int
    level: int
    level_name: str
    text: str


def load_questions() -> list[Question]:
    lines = QUESTIONS_PATH.read_text(encoding="utf-8").splitlines()
    questions: list[Question] = []
    current_level: int | None = None
    current_level_name: str = ""
    in_trap_map = False

    for line in lines:
        if line.startswith("## Trap coverage map"):
            in_trap_map = True
            continue
        if in_trap_map and line.startswith("## Level"):
            in_trap_map = False
        if in_trap_map:
            continue

        level_match = _LEVEL_HEADING.match(line)
        if level_match:
            current_level = int(level_match.group(1))
            current_level_name = level_match.group(2).strip()
            continue

        question_match = _QUESTION_LINE.match(line)
        if question_match and current_level is not None:
            questions.append(
                Question(
                    id=int(question_match.group(1)),
                    level=current_level,
                    level_name=current_level_name,
                    text=question_match.group(2).strip(),
                )
            )

    return questions


def get_question(question_id: int) -> Question | None:
    for q in load_questions():
        if q.id == question_id:
            return q
    return None
