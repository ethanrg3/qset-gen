"""Plan §5.4 / §11. Cold-start helpers."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from qset_gen.models import Attempt, SessionSignals, SetTemplate, Student
from qset_gen.selection.cold_start import (
    cold_start_weights,
    diagnostic_template,
    is_cold_start,
)
from qset_gen.selection.scoring import ScoringWeights


def _student() -> Student:
    return Student(
        student_id="stu_new",
        name="New",
        current_act_math=22.0,
        target_act_math=28.0,
    )


def test_is_cold_start_true_for_brand_new_student():
    assert is_cold_start(_student(), [], []) is True


def test_is_cold_start_false_when_has_attempts():
    history = [
        Attempt(
            student_id="stu_new", question_id="Q1",
            attempted_at=datetime.now(), correct=True, time_spent_sec=30, set_id="s",
        )
    ]
    assert is_cold_start(_student(), history, []) is False


def test_is_cold_start_false_when_has_sessions():
    sessions = [
        SessionSignals(session_id="s1", student_id="stu_new", session_date=date.today())
    ]
    assert is_cold_start(_student(), [], sessions) is False


def test_cold_start_weights_zero_resurface_and_session():
    w = cold_start_weights()
    assert w.W_RESURFACE == 0.0
    assert w.W_SESSION == 0.0
    # Other weights preserved from defaults
    assert w.W_DIFF == ScoringWeights().W_DIFF
    assert w.W_PRIORITY == ScoringWeights().W_PRIORITY


def test_diagnostic_template_relaxes_floors():
    base = SetTemplate(
        name="Mixed 20", test="ACT", size=20, sections={"Math": 1.0},
        resurface_floor=0.25, session_tie_floor=0.25,
    )
    diag = diagnostic_template(base)
    assert diag.resurface_floor == 0.0
    assert diag.session_tie_floor == 0.0
    assert "diagnostic" in diag.name
    # Distribution flatter (less weak-heavy)
    assert diag.skill_distribution["weak"] < base.skill_distribution["weak"]
    # Original unchanged
    assert base.resurface_floor == 0.25
