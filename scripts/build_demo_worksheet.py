"""Render a sample interactive worksheet to docs/sample_set.html.

Linked from docs/status.html so you can click through and see exactly what a
student receives. Uses realistic-shape ACT Math questions; the webhook URL +
secret are stubs (the Submit button will produce a fallback code instead of
posting anywhere).
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from qset_gen.models import Question, SetTemplate, Student
from qset_gen.render.render import render_set

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "sample_set.html"


def _q(qid: str, skill: str, low: float, high: float, stem: str,
       choices: list[tuple[str, str]], answer: str, explanation: str) -> Question:
    choice_html = "\n".join(
        f'<div class="choice" data-letter="{letter}">'
        f'<span class="letter">{letter}.</span> {text}</div>'
        for letter, text in choices
    )
    return Question(
        question_id=qid,
        test="ACT",
        section="Math",
        skill_tag=skill,
        difficulty_low=low,
        difficulty_high=high,
        html_render=f"<p>{stem}</p>\n{choice_html}",
        answer_key=answer,
        explanation_html=explanation,
        time_target_sec=60,
    )


def main() -> None:
    student = Student(
        student_id="stu_hank_demo",
        name="Hank (demo)",
        current_act_math=24.0,
        target_act_math=30.0,
        test_date=date.today() + timedelta(days=60),
        weak_skills=["geo_circles", "alg_quadratics"],
        strong_skills=["arith_fractions"],
    )

    template = SetTemplate(
        name="ACT Math Demo 5",
        test="ACT",
        size=5,
        sections={"Math": 1.0},
        time_limit_min=10,
    )

    questions = [
        _q(
            "ACTM-0421", "geo_circles", 24, 26,
            "A circle has area 36&pi; square units. What is its circumference?",
            [("A", "6&pi;"), ("B", "12&pi;"), ("C", "36&pi;"), ("D", "72&pi;")],
            "B",
            "<p>Area = &pi;r<sup>2</sup> = 36&pi; &rarr; r = 6. "
            "Circumference = 2&pi;r = <strong>12&pi;</strong>.</p>",
        ),
        _q(
            "ACTM-0512", "alg_quadratics", 23, 25,
            "If x<sup>2</sup> &minus; 5x + 6 = 0, what is the sum of the roots?",
            [("A", "&minus;5"), ("B", "5"), ("C", "6"), ("D", "&minus;6")],
            "B",
            "<p>For ax<sup>2</sup> + bx + c = 0, the sum of the roots is "
            "&minus;b/a = 5.</p>",
        ),
        _q(
            "ACTM-0188", "arith_fractions", 19, 21,
            "What is 2/3 + 1/4?",
            [("A", "3/7"), ("B", "1/2"), ("C", "11/12"), ("D", "5/12")],
            "C",
            "<p>Common denominator 12: 2/3 = 8/12, 1/4 = 3/12. "
            "Sum = <strong>11/12</strong>.</p>",
        ),
        _q(
            "ACTM-0633", "trig_unit_circle", 26, 28,
            "What is sin(&pi;/3)?",
            [("A", "1/2"), ("B", "&radic;2/2"), ("C", "&radic;3/2"), ("D", "1")],
            "C",
            "<p>sin(60&deg;) = sin(&pi;/3) = <strong>&radic;3/2</strong>.</p>",
        ),
        _q(
            "ACTM-0244", "alg_quadratics", 25, 27,
            "The parabola y = x<sup>2</sup> &minus; 4x + 3 has its vertex at:",
            [("A", "(2, &minus;1)"), ("B", "(&minus;2, 15)"), ("C", "(2, 1)"),
             ("D", "(4, 3)")],
            "A",
            "<p>x-coordinate of vertex = &minus;b/(2a) = 4/2 = 2. "
            "y = 4 &minus; 8 + 3 = &minus;1. Vertex = <strong>(2, &minus;1)</strong>.</p>",
        ),
    ]

    render_set(
        student=student,
        template=template,
        questions=questions,
        set_id="demo_set_phase1",
        webhook_url="https://qset-gen.example.com",  # placeholder, won't resolve
        webhook_secret="demo-secret-not-real",
        output_path=OUT,
    )
    print(f"Wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
