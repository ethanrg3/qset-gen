"""Plan §5.3 / §11. Constraint-aware sampler tests."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from qset_gen.models import Attempt, Question, SessionSignals, SetTemplate, Student
from qset_gen.selection.constraints import (
    interleave_no_streak,
    sample_set,
    violates_no_streak,
)
from qset_gen.selection.scoring import StudentContext

TODAY = date(2026, 5, 11)


def _q(qid: str, skill: str, low: float = 22, high: float = 24, section: str = "Math") -> Question:
    return Question(
        question_id=qid,
        test="ACT",
        section=section,
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


def _ctx(
    student=None,
    history=None,
    sessions=None,
    question_skill_map=None,
    directive_skill_ids=None,
) -> StudentContext:
    return StudentContext(
        student=student or _student(),
        history=history or [],
        sessions=sessions or [],
        today=TODAY,
        question_skill_map=question_skill_map or {},
        directive_skill_ids=directive_skill_ids or set(),
    )


def _template(
    size: int = 10,
    resurface_floor: float = 0.0,
    session_tie_floor: float = 0.0,
    no_streak_max: int = 2,
    sections: dict[str, float] | None = None,
) -> SetTemplate:
    return SetTemplate(
        name="test",
        test="ACT",
        size=size,
        sections=sections or {"Math": 1.0},
        resurface_floor=resurface_floor,
        session_tie_floor=session_tie_floor,
        no_streak_max=no_streak_max,
    )


# ----- violates_no_streak -----

def test_violates_no_streak_empty_picked_is_false():
    q = _q("Q1", "A")
    assert violates_no_streak([], q, no_streak_max=2) is False


def test_violates_no_streak_at_cap_blocks_same_skill():
    """Picked [A, A] at cap=2; appending another A would create streak of 3."""
    picked = [_q("Q1", "A"), _q("Q2", "A")]
    candidate = _q("Q3", "A")
    assert violates_no_streak(picked, candidate, no_streak_max=2) is True


def test_violates_no_streak_under_cap_allows_same_skill():
    picked = [_q("Q1", "A")]  # streak of 1; cap=2, so one more is OK
    candidate = _q("Q2", "A")
    assert violates_no_streak(picked, candidate, no_streak_max=2) is False


def test_violates_no_streak_different_skill_always_ok():
    picked = [_q("Q1", "A"), _q("Q2", "A"), _q("Q3", "A")]
    candidate = _q("Q4", "B")  # different skill resets streak
    assert violates_no_streak(picked, candidate, no_streak_max=2) is False


# ----- interleave_no_streak -----

def test_interleave_no_streak_breaks_up_runs():
    """Input has [A,A,A,B,B] in a row; output should never have 3 As in a row."""
    qs = [_q(f"Q{i}", "A") for i in range(3)] + [_q(f"Q{i+3}", "B") for i in range(2)]
    out = interleave_no_streak(qs, no_streak_max=2)
    # Check no run > 2
    run = 1
    for i in range(1, len(out)):
        if out[i].skill_tag == out[i - 1].skill_tag:
            run += 1
            assert run <= 2, f"streak of {run} at index {i}"
        else:
            run = 1


def test_interleave_no_streak_preserves_all_questions():
    qs = [_q(f"Q{i}", "A" if i % 2 == 0 else "B") for i in range(6)]
    out = interleave_no_streak(qs, no_streak_max=2)
    assert sorted(q.question_id for q in out) == sorted(q.question_id for q in qs)


def test_interleave_no_streak_impossible_falls_back_gracefully():
    """All-same-skill input can't satisfy no-streak. Function should return all
    questions in some order rather than infinite-loop or drop them."""
    qs = [_q(f"Q{i}", "A") for i in range(5)]
    out = interleave_no_streak(qs, no_streak_max=2)
    assert len(out) == 5


# ----- sample_set: basic -----

def test_sample_set_returns_exactly_template_size_when_pool_is_large_enough():
    candidates = [_q(f"Q{i}", f"S{i % 4}") for i in range(30)]
    out = sample_set(candidates, _template(size=10), _ctx())
    assert len(out) == 10


def test_sample_set_returns_all_when_pool_smaller_than_size():
    candidates = [_q(f"Q{i}", f"S{i % 4}") for i in range(5)]
    out = sample_set(candidates, _template(size=10), _ctx())
    assert len(out) == 5


def test_sample_set_no_duplicates():
    candidates = [_q(f"Q{i}", f"S{i % 4}") for i in range(20)]
    out = sample_set(candidates, _template(size=10), _ctx())
    ids = [q.question_id for q in out]
    assert len(ids) == len(set(ids))


def test_sample_set_respects_no_streak():
    """20 candidates across 3 skills → output should never have 3+ same in a row."""
    candidates = [_q(f"Q{i}", f"S{i % 3}") for i in range(20)]
    out = sample_set(candidates, _template(size=12, no_streak_max=2), _ctx())
    run = 1
    for i in range(1, len(out)):
        if out[i].skill_tag == out[i - 1].skill_tag:
            run += 1
            assert run <= 2
        else:
            run = 1


# ----- sample_set: floors -----

def _miss(qid: str, days_ago: int) -> Attempt:
    return Attempt(
        student_id="stu_test",
        question_id=qid,
        attempted_at=datetime.combine(TODAY - timedelta(days=days_ago), datetime.min.time()),
        correct=False,
        time_spent_sec=30,
        set_id="prev_set",
    )


def test_resurface_floor_honored_when_pool_sufficient():
    """5 candidates are resurfaceable (missed 3 days ago), 15 are fresh.
    resurface_floor=0.4 on size 10 → need ≥4 resurfaced."""
    resurface_qs = [_q(f"R{i}", f"S{i % 3}") for i in range(5)]
    fresh_qs = [_q(f"F{i}", f"S{i % 3}") for i in range(15)]
    history = [_miss(q.question_id, days_ago=3) for q in resurface_qs]
    ctx = _ctx(history=history)
    out = sample_set(
        resurface_qs + fresh_qs,
        _template(size=10, resurface_floor=0.4),
        ctx,
    )
    resurface_ids = {q.question_id for q in resurface_qs}
    hits = sum(1 for q in out if q.question_id in resurface_ids)
    assert hits >= 4


def test_resurface_floor_gracefully_caps_at_pool_size():
    """resurface_floor=0.8 but only 2 resurfaceable questions exist.
    Sampler should take all 2 and not fail."""
    resurface_qs = [_q(f"R{i}", f"S{i}") for i in range(2)]
    fresh_qs = [_q(f"F{i}", f"S{i % 3}") for i in range(20)]
    history = [_miss(q.question_id, days_ago=3) for q in resurface_qs]
    ctx = _ctx(history=history)
    out = sample_set(
        resurface_qs + fresh_qs,
        _template(size=10, resurface_floor=0.8),
        ctx,
    )
    assert len(out) == 10
    resurface_ids = {q.question_id for q in resurface_qs}
    assert sum(1 for q in out if q.question_id in resurface_ids) == 2


def test_session_tie_floor_honored():
    """A session 2 days ago introduced 'geo' and struggled 'alg'. session_tie_floor=0.5
    on size 10 → ≥5 of the picked questions must touch geo or alg."""
    tied_qs = [_q(f"T{i}", "geo" if i % 2 == 0 else "alg") for i in range(8)]
    other_qs = [_q(f"O{i}", "stat") for i in range(12)]
    sess = SessionSignals(
        session_id="sess1",
        student_id="stu_test",
        session_date=TODAY - timedelta(days=2),
        skills_introduced=["geo"],
        skills_struggled=["alg"],
    )
    out = sample_set(
        tied_qs + other_qs,
        _template(size=10, session_tie_floor=0.5),
        _ctx(sessions=[sess]),
    )
    tied_ids = {q.question_id for q in tied_qs}
    hits = sum(1 for q in out if q.question_id in tied_ids)
    assert hits >= 5


def test_session_tie_floor_only_counts_introduced_and_struggled():
    """Practiced/mastered_today don't count toward the floor (plan §5.3)."""
    practiced_qs = [_q(f"P{i}", "geo") for i in range(5)]  # 'geo' was only practiced
    other_qs = [_q(f"O{i}", "stat") for i in range(10)]
    sess = SessionSignals(
        session_id="sess1",
        student_id="stu_test",
        session_date=TODAY - timedelta(days=2),
        skills_practiced=["geo"],  # NOT introduced/struggled
    )
    out = sample_set(
        practiced_qs + other_qs,
        _template(size=10, session_tie_floor=0.6),  # demand 6 tied
        _ctx(sessions=[sess]),
    )
    # The floor can't be met because no question is "tied" by floor definition.
    # Sampler should still return 10 questions (just by score), no crash.
    assert len(out) == 10


# ----- sample_set: section mix (forward-compat for non-Math sections) -----

def test_section_mix_respects_proportions_within_plus_minus_one():
    """size=10, sections={Math:0.5, English:0.5} → expect 5 of each ±1, so [4,5,6] OK."""
    math_qs = [_q(f"M{i}", "S0", section="Math") for i in range(10)]
    english_qs = [_q(f"E{i}", "S1", section="English") for i in range(10)]
    template = SetTemplate(
        name="mixed",
        test="ACT",
        size=10,
        sections={"Math": 0.5, "English": 0.5},
        resurface_floor=0.0,
        session_tie_floor=0.0,
    )
    out = sample_set(math_qs + english_qs, template, _ctx())
    math_count = sum(1 for q in out if q.section == "Math")
    english_count = sum(1 for q in out if q.section == "English")
    assert 4 <= math_count <= 6
    assert 4 <= english_count <= 6
    assert math_count + english_count == 10
