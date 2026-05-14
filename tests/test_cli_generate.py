"""End-to-end CLI test for `qset-gen generate` against a pre-seeded local cache.

Confirms the full pipeline (cache → score → sample → render) runs without
Notion or Anthropic. Drives the CLI via Typer's CliRunner.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from typer.testing import CliRunner

from qset_gen.cache import Cache
from qset_gen.cli import app
from qset_gen.models import Question, SetTemplate, Student

runner = CliRunner()


def _seed(cache: Cache) -> None:
    cache.init_schema()
    cache.put_students([
        Student(student_id="stu_hank", name="Hank",
                current_act_math=24, target_act_math=30,
                test_date=date.today() + timedelta(days=60),
                weak_skills=[], strong_skills=[]),
    ])
    questions = []
    for i in range(30):
        questions.append(Question(
            question_id=f"Q{i:03d}", test="ACT", section="Math",
            skill_tag=f"skill_{i % 5}",
            difficulty_low=22 + (i % 5), difficulty_high=24 + (i % 5),
            html_render=f"<p>Q {i}</p>"
                         f'<div class="choice" data-letter="A">A</div>'
                         f'<div class="choice" data-letter="B">B</div>',
            answer_key="A", explanation_html=f"<p>explanation {i}</p>",
        ))
    cache.put_questions(questions)


def test_generate_produces_html_using_seeded_cache(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)

    # Minimal config pointing into the tmp project root.
    (project / "config.toml").write_text(
        '[paths]\n'
        'cache_db = "qset.db"\n'
        'output_dir = "out"\n'
        f'templates_dir = "{Path(__file__).parent.parent / "templates"}"\n'
    )

    cache = Cache(project / "qset.db")
    _seed(cache)

    # Run the CLI
    result = runner.invoke(
        app,
        ["generate", "--student", "Hank", "--template", "act_math_mixed_20"],
    )

    assert result.exit_code == 0, result.output
    assert "Generated" in result.output

    # The output file should exist and be a non-trivial HTML doc.
    out_files = list((project / "out").glob("*.html"))
    assert len(out_files) == 1
    html = out_files[0].read_text()
    assert "<!doctype html>" in html.lower()
    assert "Hank" in html
    # Should mention at least one question id.
    assert any(f"Q{i:03d}" in html for i in range(30))


def test_generate_errors_when_student_missing(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    (project / "config.toml").write_text(
        '[paths]\n'
        'cache_db = "qset.db"\n'
        f'templates_dir = "{Path(__file__).parent.parent / "templates"}"\n'
        'output_dir = "out"\n'
    )
    cache = Cache(project / "qset.db")
    cache.init_schema()  # empty
    result = runner.invoke(
        app,
        ["generate", "--student", "Nobody", "--template", "act_math_mixed_20"],
    )
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


def test_generate_flags_cold_start_for_brand_new_student(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    (project / "config.toml").write_text(
        '[paths]\n'
        'cache_db = "qset.db"\n'
        f'templates_dir = "{Path(__file__).parent.parent / "templates"}"\n'
        'output_dir = "out"\n'
    )
    cache = Cache(project / "qset.db")
    _seed(cache)  # student has no history, no sessions → cold-start
    result = runner.invoke(
        app, ["generate", "--student", "Hank", "--template", "act_math_mixed_20"],
    )
    assert result.exit_code == 0
    assert "cold-start" in result.output.lower()
