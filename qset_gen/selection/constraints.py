"""Constraint-aware sampler — plan §5.3.

Two-stage build:

  1. SELECT the set: greedy passes that prioritize hitting the resurface and
     session-tie floors first, then fill remaining slots by score. The section
     mix is enforced by capping per-section picks at the template's proportions
     (±1 question).

  2. ORDER the set: a second greedy pass reorders to satisfy the no-streak
     rule (≤ `no_streak_max` consecutive same `skill_tag`). If a configuration
     is impossible (e.g. 15 of 20 same skill), fall back to best-effort.

Splitting select from order means the SELECT stage doesn't have to think about
adjacency — it just hits floors and section caps. Cleaner to reason about and
to test.
"""

from __future__ import annotations

import math
from collections import Counter

from ..models import Question, SetTemplate
from .scoring import StudentContext, resurface_signal, session_signal


def sample_set(
    candidates_sorted: list[Question],
    template: SetTemplate,
    ctx: StudentContext,
) -> list[Question]:
    """Returns up to `template.size` questions satisfying all constraints, interleaved.

    Args:
        candidates_sorted: questions sorted by score descending. The function
          does not re-score; it trusts the input order for "preferred".
        template: set template (size, floors, no_streak_max, section mix).
        ctx: student context — used for resurface and session-tie classification.

    Returns fewer than `template.size` only if the candidate pool is too small.
    """
    size = template.size
    if size <= 0 or not candidates_sorted:
        return []

    # Pre-classify each candidate so we don't recompute signals during selection.
    resurface_ids = {q.question_id for q in candidates_sorted if resurface_signal(q, ctx) > 0}
    session_ids = {
        q.question_id for q in candidates_sorted
        if _is_session_tie(q, ctx)
    }

    resurface_pool = [q for q in candidates_sorted if q.question_id in resurface_ids]
    session_pool = [q for q in candidates_sorted if q.question_id in session_ids]

    # Required counts, capped at pool size (can't pick more than exists).
    resurface_needed = min(math.ceil(size * template.resurface_floor), len(resurface_pool))
    session_needed = min(math.ceil(size * template.session_tie_floor), len(session_pool))

    # Section caps: floor(proportion * size) + 1 (the "±1" tolerance from plan §5.3).
    section_caps = {
        section: math.floor(prop * size) + 1
        for section, prop in template.sections.items()
    }

    selected_ids: set[str] = set()
    selected: list[Question] = []
    section_counts: Counter[str] = Counter()

    def can_accept(q: Question) -> bool:
        if q.question_id in selected_ids:
            return False
        if len(selected) >= size:
            return False
        # Section cap (only enforced when the section is listed in the template).
        if q.section in section_caps and section_counts[q.section] >= section_caps[q.section]:
            return False
        return True

    def accept(q: Question) -> None:
        selected_ids.add(q.question_id)
        selected.append(q)
        section_counts[q.section] += 1

    # Pass 1: hit resurface floor.
    for q in resurface_pool:
        if sum(1 for s in selected if s.question_id in resurface_ids) >= resurface_needed:
            break
        if can_accept(q):
            accept(q)

    # Pass 2: hit session-tie floor.
    for q in session_pool:
        if sum(1 for s in selected if s.question_id in session_ids) >= session_needed:
            break
        if can_accept(q):
            accept(q)

    # Pass 3: fill remaining by score.
    for q in candidates_sorted:
        if len(selected) >= size:
            break
        if can_accept(q):
            accept(q)

    return interleave_no_streak(selected, template.no_streak_max)


def interleave_no_streak(questions: list[Question], no_streak_max: int) -> list[Question]:
    """Reorder so no run of same-skill exceeds `no_streak_max`.

    Greedy: at each position, pick the earliest remaining question whose skill
    doesn't extend the trailing streak past the limit. If no such candidate
    exists (all remaining share the trailing skill and we're already at the
    cap), accept the first remaining anyway — best effort, the alternative is
    failing on impossible inputs.

    Preserves score ordering as much as constraints allow: by walking remaining
    in input order, the highest-scored compliant question wins each slot.
    """
    if no_streak_max <= 0:
        return list(questions)

    remaining = list(questions)
    result: list[Question] = []
    while remaining:
        chosen_idx = 0  # fall-back: first remaining
        for i, q in enumerate(remaining):
            if not violates_no_streak(result, q, no_streak_max):
                chosen_idx = i
                break
        result.append(remaining.pop(chosen_idx))
    return result


def violates_no_streak(picked: list[Question], candidate: Question, no_streak_max: int) -> bool:
    """True iff appending `candidate` would create a streak > `no_streak_max`. Plan §5.3."""
    if no_streak_max <= 0:
        return True
    streak = 0
    for q in reversed(picked):
        if q.skill_tag == candidate.skill_tag:
            streak += 1
        else:
            break
    return streak >= no_streak_max


# ----- helpers -----

def _is_session_tie(q: Question, ctx: StudentContext) -> bool:
    """A question counts toward the session-tie floor iff its skill is in the
    latest session's `skills_introduced` or `skills_struggled` (plan §5.3).
    Practiced/mastered_today don't count toward the floor — only toward score.
    """
    if not ctx.sessions:
        return False
    most_recent = max(ctx.sessions, key=lambda s: s.session_date)
    days_since = (ctx.today - most_recent.session_date).days
    if days_since < 0:
        return False
    skill = q.skill_tag
    if skill in most_recent.skills_introduced and days_since <= 6:
        return True
    if skill in most_recent.skills_struggled and days_since <= 14:
        return True
    return False
