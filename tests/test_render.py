"""Plan §8.1 / §11. Renderer smoke tests."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from qset_gen.models import Question, SetTemplate, Student
from qset_gen.render.render import render_set


@pytest.fixture
def student() -> Student:
    return Student(
        student_id="stu_hank",
        name="Hank",
        current_act_math=24.0,
        target_act_math=30.0,
        test_date=date.today() + timedelta(days=60),
    )


@pytest.fixture
def template() -> SetTemplate:
    return SetTemplate(
        name="Test Mixed 5",
        test="ACT",
        size=5,
        sections={"Math": 1.0},
    )


@pytest.fixture
def questions() -> list[Question]:
    return [
        Question(
            question_id=f"Q{i}",
            test="ACT",
            section="Math",
            skill_tag=f"skill_{i}",
            difficulty_low=22,
            difficulty_high=24,
            html_render=f'<p>Question {i} stem</p>'
                        f'<div class="choice" data-letter="A">choice A</div>'
                        f'<div class="choice" data-letter="B">choice B</div>',
            answer_key="A",
            explanation_html=f"<p>Because of reason {i}.</p>",
        )
        for i in range(5)
    ]


def test_render_set_produces_html_file(tmp_path, student, template, questions):
    out = tmp_path / "set.html"
    result = render_set(
        student=student, template=template, questions=questions,
        set_id="set_test", webhook_url="https://example.com",
        webhook_secret="secret123", output_path=out,
    )
    assert result == out
    assert out.exists()
    html = out.read_text(encoding="utf-8")
    assert "<!doctype html>" in html.lower()


def test_render_contains_all_question_ids(tmp_path, student, template, questions):
    out = tmp_path / "set.html"
    render_set(
        student=student, template=template, questions=questions,
        set_id="set_test", webhook_url="https://example.com",
        webhook_secret="secret", output_path=out,
    )
    html = out.read_text(encoding="utf-8")
    for q in questions:
        assert q.question_id in html
        assert q.answer_key in html  # used by client-side scoring


def test_render_embeds_webhook_url_and_secret(tmp_path, student, template, questions):
    out = tmp_path / "set.html"
    render_set(
        student=student, template=template, questions=questions,
        set_id="set_test", webhook_url="https://qset.example.com/",
        webhook_secret="super-secret-token", output_path=out,
    )
    html = out.read_text(encoding="utf-8")
    assert "https://qset.example.com" in html  # trailing slash stripped
    assert "super-secret-token" in html
    assert "Bearer" in html  # auth header is constructed in the SPA


def test_render_embeds_student_and_set_id(tmp_path, student, template, questions):
    out = tmp_path / "set.html"
    render_set(
        student=student, template=template, questions=questions,
        set_id="set_hank_2026-05-11", webhook_url="https://e.com",
        webhook_secret="x", output_path=out,
    )
    html = out.read_text(encoding="utf-8")
    assert "stu_hank" in html
    assert "set_hank_2026-05-11" in html
    assert "Hank" in html


def test_render_creates_output_directory(tmp_path, student, template, questions):
    out = tmp_path / "subdir" / "deep" / "set.html"
    render_set(
        student=student, template=template, questions=questions,
        set_id="x", webhook_url="https://e.com", webhook_secret="x", output_path=out,
    )
    assert out.exists()
