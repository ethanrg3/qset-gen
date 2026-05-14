"""Cache roundtrip tests (plan §4.5)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from qset_gen.cache import Cache
from qset_gen.models import (
    Attempt,
    Question,
    SessionSignals,
    SkillTaxonomyEntry,
    Student,
)


@pytest.fixture
def cache(tmp_path: Path) -> Cache:
    c = Cache(tmp_path / "test.db")
    c.init_schema()
    return c


def test_questions_roundtrip(cache):
    qs = [
        Question(
            question_id=f"Q{i}",
            test="ACT",
            section="Math",
            skill_tag=f"skill_{i}",
            difficulty_low=20,
            difficulty_high=22,
            html_render=f"<p>{i}</p>",
            answer_key="A",
            explanation_html="<p>e</p>",
        )
        for i in range(3)
    ]
    cache.put_questions(qs)
    out = cache.get_questions()
    assert len(out) == 3
    assert {q.question_id for q in out} == {"Q0", "Q1", "Q2"}


def test_questions_only_active_filter(cache):
    cache.put_questions([
        Question(question_id="A", test="ACT", section="Math", skill_tag="s",
                 difficulty_low=20, difficulty_high=22, html_render="x", answer_key="A",
                 explanation_html="y", active=True),
        Question(question_id="B", test="ACT", section="Math", skill_tag="s",
                 difficulty_low=20, difficulty_high=22, html_render="x", answer_key="A",
                 explanation_html="y", active=False),
    ])
    assert {q.question_id for q in cache.get_questions(only_active=True)} == {"A"}
    assert {q.question_id for q in cache.get_questions(only_active=False)} == {"A", "B"}


def test_students_roundtrip_with_json_fields(cache):
    s = Student(
        student_id="stu_hank",
        name="Hank",
        current_act_math=24.0,
        target_act_math=30.0,
        test_date=date(2026, 7, 1),
        weak_skills=["geo", "alg"],
        strong_skills=["arith"],
    )
    cache.put_students([s])
    got = cache.get_student("stu_hank")
    assert got is not None
    assert got.name == "Hank"
    assert got.weak_skills == ["geo", "alg"]
    assert got.strong_skills == ["arith"]
    assert got.test_date == date(2026, 7, 1)


def test_get_student_by_name(cache):
    cache.put_students([
        Student(student_id="s1", name="Hank", weak_skills=[], strong_skills=[]),
        Student(student_id="s2", name="Mira", weak_skills=[], strong_skills=[]),
    ])
    assert cache.get_student_by_name("Mira").student_id == "s2"
    assert cache.get_student_by_name("Nobody") is None


def test_attempts_roundtrip(cache):
    now = datetime(2026, 5, 10, 14, 30)
    attempts = [
        Attempt(student_id="s1", question_id="Q1", attempted_at=now,
                correct=True, time_spent_sec=45, set_id="set_x"),
        Attempt(student_id="s1", question_id="Q2", attempted_at=now,
                correct=False, time_spent_sec=60, set_id="set_x", confidence="unsure"),
    ]
    cache.put_attempts(attempts)
    out = cache.get_attempts(student_id="s1")
    assert len(out) == 2
    assert {a.question_id for a in out} == {"Q1", "Q2"}
    assert any(a.confidence == "unsure" for a in out)


def test_attempts_idempotent_on_natural_key(cache):
    """INSERT OR REPLACE on (student_id, question_id, attempted_at): second put_attempts
    with the same triple updates rather than duplicates."""
    now = datetime(2026, 5, 10, 14, 30)
    a = Attempt(student_id="s1", question_id="Q1", attempted_at=now,
                correct=False, time_spent_sec=10, set_id="set_x")
    cache.put_attempts([a])
    a_updated = Attempt(student_id="s1", question_id="Q1", attempted_at=now,
                        correct=True, time_spent_sec=60, set_id="set_x")
    cache.put_attempts([a_updated])
    out = cache.get_attempts(student_id="s1")
    assert len(out) == 1
    assert out[0].correct is True
    assert out[0].time_spent_sec == 60


def test_session_signals_roundtrip(cache):
    sig = SessionSignals(
        session_id="sess_1",
        student_id="s1",
        session_date=date(2026, 5, 9),
        duration_min=60,
        skills_practiced=["geo"],
        skills_struggled=["alg"],
        skills_introduced=["trig"],
        skills_mastered_today=[],
        misconceptions=["confuses radius and diameter"],
        homework_directives=["practice unit circle"],
        extraction_model="claude-opus-4-7",
    )
    cache.put_session_signals([sig])
    out = cache.get_session_signals(student_id="s1")
    assert len(out) == 1
    assert out[0].skills_struggled == ["alg"]
    assert out[0].homework_directives == ["practice unit circle"]


def test_session_signals_ordered_most_recent_first(cache):
    sigs = [
        SessionSignals(session_id="old", student_id="s1", session_date=date(2026, 4, 1)),
        SessionSignals(session_id="new", student_id="s1", session_date=date(2026, 5, 9)),
    ]
    cache.put_session_signals(sigs)
    out = cache.get_session_signals(student_id="s1")
    assert out[0].session_id == "new"
    assert out[1].session_id == "old"


def test_taxonomy_roundtrip(cache):
    entries = [
        SkillTaxonomyEntry(skill_id="geo_circles", name="Circles", description="area, circumference"),
        SkillTaxonomyEntry(skill_id="alg_lines", name="Linear equations"),
    ]
    cache.put_skill_taxonomy(entries)
    out = cache.get_taxonomy()
    assert {e.skill_id for e in out} == {"geo_circles", "alg_lines"}
    circles = next(e for e in out if e.skill_id == "geo_circles")
    assert circles.description == "area, circumference"


def test_meta_roundtrip(cache):
    cache.set_meta("last_refresh", "2026-05-11T10:00:00")
    assert cache.get_meta("last_refresh") == "2026-05-11T10:00:00"
    assert cache.get_meta("nonexistent") is None
