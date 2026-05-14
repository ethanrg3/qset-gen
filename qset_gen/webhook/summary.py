"""Result-summary computation for /submit responses.

Kept separate so it's pure-functional and easy to test in isolation from FastAPI.
"""

from __future__ import annotations

from datetime import datetime

from ..models import Attempt, Question


def build_summary(
    attempts: list[Attempt],
    questions_by_id: dict[str, Question],
    prior_history: list[Attempt],
) -> dict:
    """Compute the response payload returned to the student's HTML.

    Returns:
        {
          "score": {"correct": int, "total": int, "pct": float},
          "by_skill": {skill_id: {"correct": int, "total": int}},
          "resurface_accuracy": {"correct": int, "total": int} | None,
        }

    A question counts as "resurfaced" if the student had at least one prior
    miss on it (in `prior_history`).
    """
    total = len(attempts)
    correct = sum(1 for a in attempts if a.correct)
    pct = (correct / total) if total else 0.0

    by_skill: dict[str, dict[str, int]] = {}
    for a in attempts:
        q = questions_by_id.get(a.question_id)
        skill = q.skill_tag if q else "unknown"
        bucket = by_skill.setdefault(skill, {"correct": 0, "total": 0})
        bucket["total"] += 1
        if a.correct:
            bucket["correct"] += 1

    prior_misses_by_q: set[str] = {a.question_id for a in prior_history if not a.correct}
    resurface_attempts = [a for a in attempts if a.question_id in prior_misses_by_q]
    resurface_summary = None
    if resurface_attempts:
        resurface_summary = {
            "correct": sum(1 for a in resurface_attempts if a.correct),
            "total": len(resurface_attempts),
        }

    return {
        "score": {"correct": correct, "total": total, "pct": round(pct, 3)},
        "by_skill": by_skill,
        "resurface_accuracy": resurface_summary,
    }


def utc_now() -> datetime:
    """Indirection so tests can patch the clock."""
    return datetime.now()
