"""Per-question scoring — plan §5.1, §5.2.

score(q, s) =
      W_DIFF      * difficulty_fit(q, s)
    + W_RESURFACE * resurface_signal(q, s)
    + W_PRIORITY  * priority_weight(q.skill, s)
    + W_SPACING   * spacing_signal(q.skill, s)
    + W_SESSION   * session_signal(q.skill, s)
    - W_RECENCY   * recency_penalty(q, s)

All signal functions take a StudentContext that carries pre-loaded history,
sessions, and a `today` date for deterministic testing. The W_* weights are
applied only in `score()`; individual signals return their unweighted [0, 1+]
value (session_signal can exceed 1.0 because of the homework-directive bonus).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from ..models import Attempt, Question, SessionSignals, Student


@dataclass(frozen=True)
class ScoringWeights:
    """Plan §5.1 default weights. Tunable via config.toml at runtime."""

    W_DIFF: float = 1.0
    W_RESURFACE: float = 1.5
    W_PRIORITY: float = 0.8
    W_SPACING: float = 0.6
    W_SESSION: float = 1.3
    W_RECENCY: float = 2.0


@dataclass
class StudentContext:
    """Everything the scorer needs to evaluate a question against a student.

    Fields beyond the core triple are precomputed by the caller so signals stay
    pure functions (easy to test, no Notion/clock side effects):

    - `today`: injectable clock — all time-based signals use this instead of
      `date.today()`.
    - `question_skill_map`: question_id → skill_tag. Lets spacing_signal find
      the most recent attempt on *any* question of a given skill without each
      attempt carrying its question's skill.
    - `directive_skill_ids`: skill_ids the caller has resolved from the most
      recent session's `homework_directives` free-text. Caller does the
      directive→skill matching (e.g. taxonomy name substring match); scoring
      just looks the result up.
    """

    student: Student
    history: list[Attempt]
    sessions: list[SessionSignals]
    today: date = field(default_factory=date.today)
    question_skill_map: dict[str, str] = field(default_factory=dict)
    directive_skill_ids: set[str] = field(default_factory=set)


# ----- §5.2 component signals -----

def difficulty_fit(
    q: Question,
    ctx: StudentContext,
    falloff: float = 4.0,
    target_offset: float = 1.0,
    prep_window_days: int = 120,
    fraction_floor: float = 0.2,
    fraction_ceil: float = 1.0,
) -> float:
    """Peaks at 1.0 when q.difficulty_mid ≈ target_for_today + 1, falls to 0 at ±falloff.

    target_for_today = current + (target − current) * progress_fraction
    progress_fraction ramps from `fraction_floor` (`prep_window_days` out from
    test) to `fraction_ceil` (on test day). Cold-start (missing scores) → 0.5.
    """
    s = ctx.student
    if s.current_act_math is None or s.target_act_math is None:
        return 0.5  # neutral default for cold-start

    progress_fraction = fraction_ceil
    if s.test_date is not None:
        days_to_test = (s.test_date - ctx.today).days
        if days_to_test >= prep_window_days:
            progress_fraction = fraction_floor
        elif days_to_test <= 0:
            progress_fraction = fraction_ceil
        else:
            ramp = 1.0 - (days_to_test / prep_window_days)  # 0 early → 1 late
            progress_fraction = fraction_floor + (fraction_ceil - fraction_floor) * ramp

    target_for_today = s.current_act_math + (s.target_act_math - s.current_act_math) * progress_fraction
    peak = target_for_today + target_offset
    distance = abs(q.difficulty_mid - peak)
    return max(0.0, 1.0 - distance / falloff)


def resurface_signal(q: Question, ctx: StudentContext) -> float:
    """1.0 in [1,6]d, 0.5 in [7,21]d, 0.2 in [22,60]d, 0 otherwise. Plan §5.2."""
    misses = [a for a in ctx.history if a.question_id == q.question_id and not a.correct]
    if not misses:
        return 0.0
    most_recent = max(misses, key=lambda a: a.attempted_at)
    days_since = _days_between(most_recent.attempted_at, ctx.today)
    if 1 <= days_since <= 6:
        return 1.0
    if 7 <= days_since <= 21:
        return 0.5
    if 22 <= days_since <= 60:
        return 0.2
    return 0.0


def priority_weight(skill_id: str, ctx: StudentContext) -> float:
    """weak=1.0, strong=0.3, neutral=0.6. Plan §5.2."""
    if skill_id in ctx.student.weak_skills:
        return 1.0
    if skill_id in ctx.student.strong_skills:
        return 0.3
    return 0.6


def spacing_signal(skill_id: str, ctx: StudentContext) -> float:
    """gap = days_since_skill / days_to_test. Optimal 10–30%. Plan §5.2."""
    s = ctx.student
    if s.test_date is None:
        return 0.1
    days_to_test = (s.test_date - ctx.today).days
    if days_to_test <= 0:
        return 0.1

    skill_attempts = [
        a for a in ctx.history
        if ctx.question_skill_map.get(a.question_id) == skill_id
    ]
    if not skill_attempts:
        return 0.1  # never seen — spacing concept doesn't apply, use floor

    most_recent = max(skill_attempts, key=lambda a: a.attempted_at)
    days_since = _days_between(most_recent.attempted_at, ctx.today)
    if days_since < 0:
        return 0.1
    gap = days_since / days_to_test
    if 0.10 <= gap <= 0.30:
        return 1.0
    if 0.05 <= gap < 0.10 or 0.30 < gap <= 0.50:
        return 0.5
    return 0.1


def session_signal(
    skill_id: str,
    ctx: StudentContext,
    directive_bonus: float = 0.4,
    decay_window_days: int = 14,
) -> float:
    """Most recent session's signal for this skill, linearly decayed.

    Base values per category (introduced/struggled within window):
      introduced + ≤6d → 1.0
      struggled  + ≤14d → 0.9
      practiced  + ≤14d → 0.5
      mastered_today + ≤6d → 0.3

    Linear decay across [day-1=full, day-14=0]. Then add a flat `directive_bonus`
    if this skill is in `ctx.directive_skill_ids` (homework directive named it).
    Plan §5.2.
    """
    if not ctx.sessions:
        return 0.0

    most_recent = max(ctx.sessions, key=lambda s: s.session_date)
    days_since = (ctx.today - most_recent.session_date).days
    if days_since < 0:
        return 0.0

    candidates: list[float] = []
    if skill_id in most_recent.skills_introduced and days_since <= 6:
        candidates.append(1.0)
    if skill_id in most_recent.skills_struggled and days_since <= 14:
        candidates.append(0.9)
    if skill_id in most_recent.skills_practiced and days_since <= 14:
        candidates.append(0.5)
    if skill_id in most_recent.skills_mastered_today and days_since <= 6:
        candidates.append(0.3)

    base = max(candidates) if candidates else 0.0
    decay = _linear_decay(days_since, decay_window_days)
    value = base * decay

    if skill_id in ctx.directive_skill_ids:
        value += directive_bonus

    return value


def recency_penalty(q: Question, ctx: StudentContext) -> float:
    """Avoid recent CORRECT answers; misses are not penalized (resurface owns that). Plan §5.2."""
    correct_attempts = [
        a for a in ctx.history
        if a.question_id == q.question_id and a.correct
    ]
    if not correct_attempts:
        return 0.0
    most_recent = max(correct_attempts, key=lambda a: a.attempted_at)
    days_since = _days_between(most_recent.attempted_at, ctx.today)
    if days_since < 0:
        return 0.0
    if days_since <= 7:
        return 1.0
    if days_since <= 30:
        return 0.5
    return 0.0


# ----- §5.1 composed score -----

def score(q: Question, ctx: StudentContext, weights: ScoringWeights) -> float:
    return (
        weights.W_DIFF * difficulty_fit(q, ctx)
        + weights.W_RESURFACE * resurface_signal(q, ctx)
        + weights.W_PRIORITY * priority_weight(q.skill_tag, ctx)
        + weights.W_SPACING * spacing_signal(q.skill_tag, ctx)
        + weights.W_SESSION * session_signal(q.skill_tag, ctx)
        - weights.W_RECENCY * recency_penalty(q, ctx)
    )


# ----- helpers -----

def _days_between(past: datetime, today: date) -> int:
    """Days between a past datetime and `today` (a date), floored to days."""
    today_dt = datetime.combine(today, datetime.min.time())
    if past.tzinfo is not None:
        today_dt = today_dt.replace(tzinfo=past.tzinfo)
    return (today_dt - past).days


def _linear_decay(days_since: int, window_days: int) -> float:
    """day-0 and day-1 → 1.0; day-N (window_days) → 0.0; linear between; clamped."""
    if days_since <= 1:
        return 1.0
    if days_since >= window_days:
        return 0.0
    return 1.0 - (days_since - 1) / (window_days - 1)
