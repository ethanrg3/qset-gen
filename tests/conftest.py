"""Shared pytest fixtures."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from qset_gen.models import Question, SessionSignals, Student

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def templates_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "templates"


@pytest.fixture
def sample_student() -> Student:
    return Student(
        student_id="stu_hank",
        name="Hank",
        current_act_math=24.0,
        target_act_math=30.0,
        test_date=date.today() + timedelta(days=60),
        weak_skills=["geo_circles", "alg_quadratics"],
        strong_skills=["arith_fractions"],
    )


@pytest.fixture
def sample_questions() -> list[Question]:
    return [
        Question(
            question_id=f"ACTM-{i:04d}",
            test="ACT",
            section="Math",
            skill_tag=skill,
            difficulty_low=low,
            difficulty_high=low + 2,
            html_render=f"<p>Q{i}</p>",
            answer_key="A",
            explanation_html=f"<p>explanation {i}</p>",
            time_target_sec=60,
        )
        for i, (skill, low) in enumerate(
            [
                ("geo_circles", 22),
                ("alg_quadratics", 24),
                ("arith_fractions", 18),
                ("trig_unit_circle", 28),
                ("stat_mean", 20),
            ],
            start=1,
        )
    ]


@pytest.fixture
def sample_session_signals() -> SessionSignals:
    return SessionSignals(
        session_id="sess_2026-05-08_hank",
        student_id="stu_hank",
        session_date=date.today() - timedelta(days=2),
        duration_min=60,
        skills_practiced=["geo_circles", "alg_quadratics"],
        skills_struggled=["geo_circles"],
        skills_introduced=["trig_unit_circle"],
        skills_mastered_today=[],
        misconceptions=["confuses radius and diameter in area formula"],
        homework_directives=["practice unit-circle problems this week"],
        extraction_model="claude-opus-4-7",
    )
