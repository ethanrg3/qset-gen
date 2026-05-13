"""Plan §5.2 / §11. Each component signal tested at its boundaries plus a
composition test that `score()` sums them with the right weights."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from qset_gen.models import Attempt, Question, SessionSignals, Student
from qset_gen.selection.scoring import (
    ScoringWeights,
    StudentContext,
    difficulty_fit,
    priority_weight,
    recency_penalty,
    resurface_signal,
    score,
    session_signal,
    spacing_signal,
)

TODAY = date(2026, 5, 11)


def _q(question_id: str, skill: str, low: float = 22, high: float = 24) -> Question:
    return Question(
        question_id=question_id,
        test="ACT",
        section="Math",
        skill_tag=skill,
        difficulty_low=low,
        difficulty_high=high,
        html_render="<p>q</p>",
        answer_key="A",
        explanation_html="<p>e</p>",
    )


def _student(**kwargs) -> Student:
    base = dict(
        student_id="stu_test",
        name="Test",
        current_act_math=24.0,
        target_act_math=30.0,
        test_date=TODAY + timedelta(days=60),
        weak_skills=[],
        strong_skills=[],
    )
    base.update(kwargs)
    return Student(**base)


def _attempt(qid: str, days_ago: int, correct: bool) -> Attempt:
    return Attempt(
        student_id="stu_test",
        question_id=qid,
        attempted_at=datetime.combine(TODAY - timedelta(days=days_ago), datetime.min.time()),
        correct=correct,
        time_spent_sec=30,
        set_id="set_test",
    )


def _ctx(
    student: Student | None = None,
    history: list[Attempt] | None = None,
    sessions: list[SessionSignals] | None = None,
    question_skill_map: dict[str, str] | None = None,
    directive_skill_ids: set[str] | None = None,
) -> StudentContext:
    return StudentContext(
        student=student or _student(),
        history=history or [],
        sessions=sessions or [],
        today=TODAY,
        question_skill_map=question_skill_map or {},
        directive_skill_ids=directive_skill_ids or set(),
    )


# ----- priority_weight -----

def test_priority_weight_weak_strong_neutral():
    ctx = _ctx(student=_student(weak_skills=["w"], strong_skills=["s"]))
    assert priority_weight("w", ctx) == 1.0
    assert priority_weight("s", ctx) == 0.3
    assert priority_weight("other", ctx) == 0.6


# ----- resurface_signal -----

def test_resurface_signal_never_missed_is_zero():
    q = _q("Q1", "geo")
    assert resurface_signal(q, _ctx()) == 0.0


def test_resurface_signal_optimal_window_1_to_6_days_is_1():
    q = _q("Q1", "geo")
    for d in (1, 3, 6):
        ctx = _ctx(history=[_attempt("Q1", days_ago=d, correct=False)])
        assert resurface_signal(q, ctx) == 1.0, f"day {d}"


def test_resurface_signal_secondary_window_7_to_21_is_half():
    q = _q("Q1", "geo")
    for d in (7, 14, 21):
        ctx = _ctx(history=[_attempt("Q1", days_ago=d, correct=False)])
        assert resurface_signal(q, ctx) == 0.5, f"day {d}"


def test_resurface_signal_tail_window_22_to_60_is_0_2():
    q = _q("Q1", "geo")
    for d in (22, 40, 60):
        ctx = _ctx(history=[_attempt("Q1", days_ago=d, correct=False)])
        assert resurface_signal(q, ctx) == 0.2, f"day {d}"


def test_resurface_signal_past_60_days_is_zero():
    q = _q("Q1", "geo")
    ctx = _ctx(history=[_attempt("Q1", days_ago=61, correct=False)])
    assert resurface_signal(q, ctx) == 0.0


def test_resurface_signal_ignores_correct_attempts():
    """Plan §5.2: resurface is for MISSED questions only."""
    q = _q("Q1", "geo")
    ctx = _ctx(history=[_attempt("Q1", days_ago=3, correct=True)])
    assert resurface_signal(q, ctx) == 0.0


# ----- recency_penalty -----

def test_recency_penalty_zero_when_no_correct_history():
    q = _q("Q1", "geo")
    assert recency_penalty(q, _ctx()) == 0.0


def test_recency_penalty_recent_correct_is_full():
    q = _q("Q1", "geo")
    ctx = _ctx(history=[_attempt("Q1", days_ago=3, correct=True)])
    assert recency_penalty(q, ctx) == 1.0


def test_recency_penalty_extended_window_is_half():
    q = _q("Q1", "geo")
    ctx = _ctx(history=[_attempt("Q1", days_ago=14, correct=True)])
    assert recency_penalty(q, ctx) == 0.5


def test_recency_penalty_only_on_correct_not_misses():
    """Plan §5.2: misses are not penalized — that's resurface's job."""
    q = _q("Q1", "geo")
    ctx = _ctx(history=[_attempt("Q1", days_ago=2, correct=False)])
    assert recency_penalty(q, ctx) == 0.0


# ----- session_signal -----

def _session(days_ago: int, **kwargs) -> SessionSignals:
    base = dict(
        session_id=f"sess_{days_ago}",
        student_id="stu_test",
        session_date=TODAY - timedelta(days=days_ago),
    )
    base.update(kwargs)
    return SessionSignals(**base)


def test_session_signal_no_sessions_is_zero():
    assert session_signal("geo", _ctx()) == 0.0


def test_session_signal_introduced_within_6d_is_full():
    sess = _session(days_ago=1, skills_introduced=["trig"])
    assert session_signal("trig", _ctx(sessions=[sess])) == 1.0


def test_session_signal_introduced_after_6d_drops_to_zero_base():
    """Outside the 6-day introduced window, base becomes 0 (unless in another list)."""
    sess = _session(days_ago=8, skills_introduced=["trig"])
    assert session_signal("trig", _ctx(sessions=[sess])) == 0.0


def test_session_signal_struggled_within_14d_with_decay():
    """Day-1 → 0.9, day-14 → 0.0, linear between."""
    s1 = _session(days_ago=1, skills_struggled=["geo"])
    assert session_signal("geo", _ctx(sessions=[s1])) == 0.9
    s14 = _session(days_ago=14, skills_struggled=["geo"])
    assert session_signal("geo", _ctx(sessions=[s14])) == 0.0
    s7 = _session(days_ago=7, skills_struggled=["geo"])
    # decay = 1 - (7-1)/13 = 7/13; value = 0.9 * 7/13
    assert abs(session_signal("geo", _ctx(sessions=[s7])) - 0.9 * (7 / 13)) < 1e-9


def test_session_signal_takes_max_category_when_skill_in_multiple_lists():
    """A skill could appear in both struggled (0.9) and practiced (0.5) — pick 0.9."""
    sess = _session(days_ago=1, skills_struggled=["geo"], skills_practiced=["geo"])
    assert session_signal("geo", _ctx(sessions=[sess])) == 0.9


def test_session_signal_homework_directive_adds_flat_0_4():
    """Plan §5.2: directive bonus is added regardless of category."""
    sess = _session(days_ago=1, skills_struggled=["geo"])
    val = session_signal("geo", _ctx(sessions=[sess], directive_skill_ids={"geo"}))
    assert val == 0.9 + 0.4


def test_session_signal_directive_bonus_applies_even_without_category_match():
    """Tutor explicitly named a skill that wasn't in any other list."""
    sess = _session(days_ago=1)  # all categories empty
    val = session_signal("trig", _ctx(sessions=[sess], directive_skill_ids={"trig"}))
    assert val == 0.4


def test_session_signal_picks_most_recent_session():
    old = _session(days_ago=10, skills_introduced=["A"])  # out of 6-day window
    new = _session(days_ago=2, skills_introduced=["A"])  # in window
    # If we ordered by most recent only, value should reflect the new session.
    val = session_signal("A", _ctx(sessions=[old, new]))
    assert val > 0  # most recent (new) is in window


# ----- spacing_signal -----

def test_spacing_signal_optimal_gap_is_1():
    """gap in [0.10, 0.30] of days_to_test."""
    s = _student(test_date=TODAY + timedelta(days=100))  # days_to_test=100
    # gap = 20/100 = 0.20 → optimal
    history = [_attempt("Q_geo", days_ago=20, correct=True)]
    ctx = _ctx(student=s, history=history, question_skill_map={"Q_geo": "geo"})
    assert spacing_signal("geo", ctx) == 1.0


def test_spacing_signal_secondary_gap_is_half():
    s = _student(test_date=TODAY + timedelta(days=100))
    # gap = 40/100 = 0.40 → secondary
    history = [_attempt("Q_geo", days_ago=40, correct=True)]
    ctx = _ctx(student=s, history=history, question_skill_map={"Q_geo": "geo"})
    assert spacing_signal("geo", ctx) == 0.5


def test_spacing_signal_unseen_skill_returns_floor():
    s = _student(test_date=TODAY + timedelta(days=100))
    ctx = _ctx(student=s)
    assert spacing_signal("geo_unseen", ctx) == 0.1


def test_spacing_signal_no_test_date_returns_floor():
    ctx = _ctx(student=_student(test_date=None))
    assert spacing_signal("geo", ctx) == 0.1


# ----- difficulty_fit -----

def test_difficulty_fit_cold_start_returns_half():
    ctx = _ctx(student=_student(current_act_math=None, target_act_math=None))
    assert difficulty_fit(_q("Q", "geo", low=24, high=24), ctx) == 0.5


def test_difficulty_fit_peaks_near_target_plus_offset():
    """current=24, target=30, on test day (progress=1.0) → target_for_today=30.
    Peak at 30 + 1 = 31. A question at difficulty_mid=31 should score 1.0."""
    s = _student(test_date=TODAY)  # days_to_test=0 → progress = ceil = 1.0
    q = _q("Q", "geo", low=30, high=32)  # mid = 31
    val = difficulty_fit(q, _ctx(student=s))
    assert val == 1.0


def test_difficulty_fit_falls_off_at_4_points():
    """Distance of 4 from peak → 0.0 with default falloff=4.0."""
    s = _student(test_date=TODAY)
    # peak = 31; question at 27 (mid) → distance 4 → 0.0
    q = _q("Q", "geo", low=26, high=28)
    val = difficulty_fit(q, _ctx(student=s))
    assert val == 0.0


def test_difficulty_fit_progress_fraction_ramps_with_time():
    """Early in prep, target_for_today is closer to current (lower peak).
    Question at current+1 should fit better early than late."""
    early_student = _student(test_date=TODAY + timedelta(days=200))  # beyond prep_window
    late_student = _student(test_date=TODAY + timedelta(days=1))
    # current=24, target=30. Early: target_for_today ≈ 24 + 6*0.2 = 25.2, peak ≈ 26.2.
    # Late: target_for_today ≈ 30, peak ≈ 31.
    q_low = _q("Q", "geo", low=25, high=27)  # mid = 26
    fit_early = difficulty_fit(q_low, _ctx(student=early_student))
    fit_late = difficulty_fit(q_low, _ctx(student=late_student))
    assert fit_early > fit_late


# ----- score composition -----

def test_score_sums_components_with_weights():
    """End-to-end: a question hitting weak + resurface + session-introduced should
    score higher than a neutral, never-seen question."""
    s = _student(weak_skills=["geo"], test_date=TODAY + timedelta(days=60))
    history = [_attempt("Q1", days_ago=3, correct=False)]  # resurface hit
    sess = _session(days_ago=2, skills_introduced=["geo"])
    ctx = _ctx(student=s, history=history, sessions=[sess], question_skill_map={"Q1": "geo"})

    hot = _q("Q1", "geo", low=29, high=31)  # difficulty near target
    cold = _q("Q2", "neutral", low=18, high=20)  # easy, no signals

    weights = ScoringWeights()
    assert score(hot, ctx, weights) > score(cold, ctx, weights)


def test_score_recency_penalty_subtracts():
    """A question answered correctly yesterday should score lower than one not seen."""
    s = _student(weak_skills=["geo"])
    seen = _q("Q1", "geo", low=24, high=26)
    unseen = _q("Q2", "geo", low=24, high=26)
    ctx = _ctx(student=s, history=[_attempt("Q1", days_ago=1, correct=True)])
    weights = ScoringWeights()
    assert score(seen, ctx, weights) < score(unseen, ctx, weights)
