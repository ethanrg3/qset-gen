"""Per-question scoring — plan §5.1, §5.2.

score(q, s) =
      W_DIFF      * difficulty_fit(q, s)
    + W_RESURFACE * resurface_signal(q, s)
    + W_PRIORITY  * priority_weight(q.skill, s)
    + W_SPACING   * spacing_signal(q.skill, s)
    + W_SESSION   * session_signal(q.skill, s)
    - W_RECENCY   * recency_penalty(q, s)
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models import Attempt, Question, SessionSignals, Student


@dataclass(frozen=True)
class ScoringWeights:
    W_DIFF: float = 1.0
    W_RESURFACE: float = 1.5
    W_PRIORITY: float = 0.8
    W_SPACING: float = 0.6
    W_SESSION: float = 1.3
    W_RECENCY: float = 2.0


@dataclass
class StudentContext:
    """Everything the scorer needs to evaluate a question against a student."""

    student: Student
    history: list[Attempt]
    sessions: list[SessionSignals]


def difficulty_fit(q: Question, ctx: StudentContext, falloff: float = 4.0) -> float:
    """§5.2. Peaks at 1.0 when q.difficulty_mid ≈ target_for_today + 1, falls to 0 at ±falloff."""
    raise NotImplementedError


def resurface_signal(q: Question, ctx: StudentContext) -> float:
    """§5.2. 1.0 in [1,6]d, 0.5 in [7,21]d, 0.2 in [22,60]d, 0 otherwise."""
    raise NotImplementedError


def priority_weight(skill_id: str, ctx: StudentContext) -> float:
    """§5.2. weak=1.0, strong=0.3, neutral=0.6."""
    raise NotImplementedError


def spacing_signal(skill_id: str, ctx: StudentContext) -> float:
    """§5.2. Gap = days_since_skill / days_to_test. Optimal 10–30%."""
    raise NotImplementedError


def session_signal(skill_id: str, ctx: StudentContext) -> float:
    """§5.2. Lookups in most recent session within last 14d, with linear decay.

    introduced + ≤6d → 1.0
    struggled + ≤14d → 0.9
    practiced + ≤14d → 0.5
    mastered_today + ≤6d → 0.3
    homework_directive bonus → +0.4 flat
    """
    raise NotImplementedError


def recency_penalty(q: Question, ctx: StudentContext) -> float:
    """§5.2. Avoid recent CORRECT answers; misses are not penalized (resurface owns that)."""
    raise NotImplementedError


def score(q: Question, ctx: StudentContext, weights: ScoringWeights) -> float:
    return (
        weights.W_DIFF * difficulty_fit(q, ctx)
        + weights.W_RESURFACE * resurface_signal(q, ctx)
        + weights.W_PRIORITY * priority_weight(q.skill_tag, ctx)
        + weights.W_SPACING * spacing_signal(q.skill_tag, ctx)
        + weights.W_SESSION * session_signal(q.skill_tag, ctx)
        - weights.W_RECENCY * recency_penalty(q, ctx)
    )
