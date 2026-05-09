"""Constraint-aware sampler — plan §5.3.

Greedy walk down score-sorted candidates, accepting only if:
  - no-streak: ≤2 consecutive same skill_tag
  - section-mix: respect template proportions ±1
  - resurface_floor: ≥X% of set is resurfaced misses (when student has miss history)
  - session_tie_floor: ≥X% touches a recent session-introduced/struggled skill
"""

from __future__ import annotations

from ..models import Question, SetTemplate
from .scoring import StudentContext


def sample_set(
    candidates_sorted: list[Question],
    template: SetTemplate,
    ctx: StudentContext,
) -> list[Question]:
    """Returns `template.size` questions satisfying all constraints, interleaved.

    Args:
        candidates_sorted: questions sorted by score descending
        template: set template (size, floors, no_streak_max, etc.)
        ctx: student context (used for resurface/session-tie floor checks)
    """
    raise NotImplementedError


def violates_no_streak(picked: list[Question], candidate: Question, no_streak_max: int) -> bool:
    """Plan §5.3 rule 1."""
    raise NotImplementedError
