"""Smoke tests for pydantic models. Real behavior tests live in test_scoring etc."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from qset_gen.models import Question, SetTemplate


def test_question_difficulty_mid(sample_questions):
    q = sample_questions[0]
    assert q.difficulty_mid == (q.difficulty_low + q.difficulty_high) / 2


def test_set_template_proportions_must_sum_to_one():
    with pytest.raises(ValidationError):
        SetTemplate(
            name="bad",
            test="ACT",
            size=10,
            sections={"Math": 0.5, "English": 0.3},  # sums to 0.8
        )


def test_set_template_default_floors():
    t = SetTemplate(name="ok", test="ACT", size=10, sections={"Math": 1.0})
    assert t.no_streak_max == 2
    assert t.ordering == "interleaved"
