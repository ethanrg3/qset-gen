"""Plan §6.4. Adaptive weak/strong recompute tests."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from qset_gen.adapt.weak_strong import (
    STATUS_NEUTRAL,
    STATUS_STRONG,
    STATUS_WEAK,
    AdaptParams,
    recompute_weak_strong,
    rolling_accuracy,
    weakness_score,
)
from qset_gen.models import Attempt, SessionSignals, SkillTaxonomyEntry, Student

TODAY = date(2026, 5, 11)


def _student(weak=None, strong=None) -> Student:
    return Student(
        student_id="stu_test",
        name="Test",
        current_act_math=24.0,
        target_act_math=30.0,
        weak_skills=weak or [],
        strong_skills=strong or [],
    )


def _attempt(qid: str, days_ago: int, correct: bool) -> Attempt:
    return Attempt(
        student_id="stu_test",
        question_id=qid,
        attempted_at=datetime.combine(TODAY - timedelta(days=days_ago), datetime.min.time()),
        correct=correct,
        time_spent_sec=30,
        set_id="set_x",
    )


def _session(days_ago: int, **lists) -> SessionSignals:
    base = dict(
        session_id=f"sess_{days_ago}",
        student_id="stu_test",
        session_date=TODAY - timedelta(days=days_ago),
    )
    base.update(lists)
    return SessionSignals(**base)


def _tax(*skill_ids: str) -> list[SkillTaxonomyEntry]:
    return [SkillTaxonomyEntry(skill_id=s, name=s) for s in skill_ids]


# ----- rolling_accuracy -----

def test_rolling_accuracy_cold_start_returns_half():
    acc, n = rolling_accuracy(
        skill_id="geo", history=[], question_skill_map={}, today=TODAY, params=AdaptParams()
    )
    assert acc == 0.5
    assert n == 0


def test_rolling_accuracy_all_correct_is_one():
    history = [_attempt(f"Q{i}", days_ago=i, correct=True) for i in range(5)]
    qmap = {a.question_id: "geo" for a in history}
    acc, n = rolling_accuracy(
        skill_id="geo", history=history, question_skill_map=qmap, today=TODAY, params=AdaptParams()
    )
    assert acc == 1.0
    assert n == 5


def test_rolling_accuracy_all_wrong_is_zero():
    history = [_attempt(f"Q{i}", days_ago=i, correct=False) for i in range(5)]
    qmap = {a.question_id: "geo" for a in history}
    acc, _ = rolling_accuracy(
        skill_id="geo", history=history, question_skill_map=qmap, today=TODAY, params=AdaptParams()
    )
    assert acc == 0.0


def test_rolling_accuracy_caps_at_window_size():
    history = [_attempt(f"Q{i}", days_ago=i, correct=True) for i in range(30)]
    qmap = {a.question_id: "geo" for a in history}
    _, n = rolling_accuracy(
        skill_id="geo", history=history, question_skill_map=qmap, today=TODAY, params=AdaptParams()
    )
    assert n == 20  # window default


def test_rolling_accuracy_weights_recent_more():
    """Recent miss + old correct should yield accuracy < 0.5."""
    history = [
        _attempt("Q1", days_ago=0, correct=False),
        _attempt("Q2", days_ago=30, correct=True),
    ]
    qmap = {"Q1": "geo", "Q2": "geo"}
    acc, _ = rolling_accuracy(
        skill_id="geo", history=history, question_skill_map=qmap, today=TODAY, params=AdaptParams()
    )
    assert acc < 0.5


# ----- weakness_score -----

def test_weakness_score_no_data_is_low():
    """No attempts, no sessions → score ≈ 0.5 * (1 - 0.5) = 0.25, evidence = 0."""
    score, evidence = weakness_score(
        skill_id="geo", history=[], sessions=[], params=AdaptParams(), today=TODAY
    )
    assert abs(score - 0.25) < 1e-9
    assert evidence == 0


def test_weakness_score_repeated_misses_pushes_score_up():
    history = [_attempt(f"Q{i}", days_ago=i, correct=False) for i in range(10)]
    qmap = {a.question_id: "geo" for a in history}
    score, evidence = weakness_score(
        skill_id="geo", history=history, sessions=[], params=AdaptParams(),
        question_skill_map=qmap, today=TODAY,
    )
    assert score >= 0.5  # α=0.5, accuracy=0 → 0.5 just from accuracy component
    assert evidence == 10


def test_weakness_score_session_struggle_increases_score():
    sessions = [_session(days_ago=2, skills_struggled=["geo"]) for _ in range(3)]
    score, evidence = weakness_score(
        skill_id="geo", history=[], sessions=sessions, params=AdaptParams(), today=TODAY
    )
    # accuracy=0.5 cold → 0.5*0.5 = 0.25; struggle_density=1.0 → +0.4; total ≈ 0.65
    assert score > 0.6
    assert evidence == 3


def test_weakness_score_session_mastery_decreases_score():
    sessions = [_session(days_ago=2, skills_mastered_today=["geo"]) for _ in range(3)]
    score, _ = weakness_score(
        skill_id="geo", history=[], sessions=sessions, params=AdaptParams(), today=TODAY
    )
    # 0.25 (from accuracy) - 0.2*1.0 (mastery) = 0.05
    assert score < 0.15


# ----- recompute_weak_strong -----

def test_recompute_promotes_skill_to_weak_after_misses_and_session_struggle():
    student = _student()
    history = [_attempt(f"Q{i}", days_ago=i, correct=False) for i in range(5)]
    qmap = {a.question_id: "geo" for a in history}
    sessions = [_session(days_ago=2, skills_struggled=["geo"])]

    new_weak, new_strong, changes = recompute_weak_strong(
        student=student, history=history, sessions=sessions,
        taxonomy=_tax("geo", "stat"), params=AdaptParams(),
        question_skill_map=qmap, today=TODAY,
    )
    assert "geo" in new_weak
    assert "geo" not in new_strong
    geo_changes = [c for c in changes if c.skill_id == "geo"]
    assert len(geo_changes) == 1
    assert geo_changes[0].prior_status == STATUS_NEUTRAL
    assert geo_changes[0].new_status == STATUS_WEAK


def test_recompute_demotes_skill_from_weak_after_session_mastery():
    student = _student(weak=["geo"])
    # Many recent correct attempts + a mastered session
    history = [_attempt(f"Q{i}", days_ago=i, correct=True) for i in range(8)]
    qmap = {a.question_id: "geo" for a in history}
    sessions = [_session(days_ago=1, skills_mastered_today=["geo"])]

    new_weak, new_strong, changes = recompute_weak_strong(
        student=student, history=history, sessions=sessions,
        taxonomy=_tax("geo"), params=AdaptParams(),
        question_skill_map=qmap, today=TODAY,
    )
    assert "geo" not in new_weak
    assert "geo" in new_strong
    geo_changes = [c for c in changes if c.skill_id == "geo"]
    assert geo_changes[0].prior_status == STATUS_WEAK
    assert geo_changes[0].new_status == STATUS_STRONG


def test_recompute_min_evidence_gates_promotion():
    """One miss and no sessions → 1 evidence point < min_evidence_points (default 5) → stays neutral."""
    student = _student()
    history = [_attempt("Q1", days_ago=1, correct=False)]
    qmap = {"Q1": "geo"}

    new_weak, _, changes = recompute_weak_strong(
        student=student, history=history, sessions=[],
        taxonomy=_tax("geo"), params=AdaptParams(),
        question_skill_map=qmap, today=TODAY,
    )
    assert "geo" not in new_weak
    assert all(c.new_status == STATUS_NEUTRAL for c in changes if c.skill_id == "geo")


def test_recompute_returns_no_changes_when_status_unchanged():
    """If a skill is already weak and stays weak, no change is recorded."""
    student = _student(weak=["geo"])
    history = [_attempt(f"Q{i}", days_ago=i, correct=False) for i in range(8)]
    qmap = {a.question_id: "geo" for a in history}
    sessions = [_session(days_ago=2, skills_struggled=["geo"])]

    new_weak, _, changes = recompute_weak_strong(
        student=student, history=history, sessions=sessions,
        taxonomy=_tax("geo"), params=AdaptParams(),
        question_skill_map=qmap, today=TODAY,
    )
    assert "geo" in new_weak
    # geo was weak before, weak after → no change row
    assert not any(c.skill_id == "geo" for c in changes)


def test_recompute_ignores_old_sessions_beyond_cutoff():
    """A struggled session 90 days ago shouldn't push current weakness."""
    student = _student()
    sessions = [_session(days_ago=90, skills_struggled=["geo"]) for _ in range(10)]

    new_weak, _, _ = recompute_weak_strong(
        student=student, history=[], sessions=sessions,
        taxonomy=_tax("geo"), params=AdaptParams(), today=TODAY,
    )
    assert "geo" not in new_weak
