"""Cold-start handling — plan §5.4.

A new student has no Q-History and no Session Signals. In that case:
- Skip resurface and session signals (set W_RESURFACE=0, W_SESSION=0).
- Use baseline difficulty band current_act_math ± 3.
- First N sets are diagnostic-leaning (broader skill coverage, less weak-area
  weighting); flag as `diagnostic=true`.

This module exposes:
- `is_cold_start(student, history, sessions)`: detection.
- `cold_start_weights()`: ScoringWeights with resurface and session zeroed out.
- `diagnostic_template(base)`: relaxes skill_distribution + floors so the set
  covers more skills evenly while the system gathers data.
"""

from __future__ import annotations

from ..models import Attempt, SessionSignals, SetTemplate, Student
from .scoring import ScoringWeights

DEFAULT_DIAGNOSTIC_SET_COUNT = 3


def is_cold_start(
    student: Student,
    history: list[Attempt],
    sessions: list[SessionSignals],
    *,
    diagnostic_set_count: int = DEFAULT_DIAGNOSTIC_SET_COUNT,
) -> bool:
    """Cold-start = no attempts and no sessions yet. The diagnostic_set_count
    parameter is reserved for the future (when we want to keep cold-start mode
    on for the first N sets even after some attempts exist); v1 just checks for
    absence of any prior data."""
    if history:
        return False
    if sessions:
        return False
    _ = diagnostic_set_count  # currently unused; documented for forward compat
    return True


def cold_start_weights(base: ScoringWeights | None = None) -> ScoringWeights:
    """Zero out signals that need history we don't have yet.

    Keeps W_DIFF (difficulty fit still works), W_PRIORITY (manual weak/strong
    at intake still informs), and W_RECENCY (zeros out naturally — no history
    means no penalty). W_SPACING falls back to its floor 0.1 inside the signal
    so we leave the weight but the value will be muted.
    """
    base = base or ScoringWeights()
    return ScoringWeights(
        W_DIFF=base.W_DIFF,
        W_RESURFACE=0.0,
        W_PRIORITY=base.W_PRIORITY,
        W_SPACING=base.W_SPACING,
        W_SESSION=0.0,
        W_RECENCY=base.W_RECENCY,
    )


def diagnostic_template(base: SetTemplate) -> SetTemplate:
    """Return a relaxed copy of `base` suited for diagnostic-leaning sets.

    Broadens skill coverage by flattening weak/neutral/strong distribution and
    dropping the resurface/session-tie floors (we have nothing to resurface or
    tie to yet). `no_streak_max` stays from the base; `name` gets a suffix so
    set_ids carry the signal.
    """
    return base.model_copy(update={
        "name": f"{base.name} (diagnostic)",
        "skill_distribution": {"weak": 0.4, "neutral": 0.5, "strong": 0.1},
        "resurface_floor": 0.0,
        "session_tie_floor": 0.0,
    })
