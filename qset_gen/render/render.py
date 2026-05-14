"""HTML renderer — plan §8.1, §8.2.

Produces a single self-contained HTML file: question payload, choice handlers,
timer, navigation, results screen — all inlined in `set_shell.html.j2`. Vanilla
JS, no build step. The student opens it in a browser, works through it, and
clicks Submit, which POSTs to the FastAPI webhook URL baked in at render time.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..models import Question, SetTemplate, Student

_DEFAULT_TEMPLATE_DIR = Path(__file__).parent


def render_set(
    *,
    student: Student,
    template: SetTemplate,
    questions: list[Question],
    set_id: str,
    webhook_url: str,
    webhook_secret: str,
    output_path: Path,
    template_dir: Path | None = None,
) -> Path:
    """Render the question set to a self-contained HTML file. Returns output_path.

    The HTML embeds:
      - Per-question payload (id, html_render, answer_key, explanation_html, skill_tag, time_target)
      - Webhook URL and secret (used as Bearer token on submit)
      - Student id+name and set_id (echoed in the POST body)
    """
    env = _make_env(template_dir or _DEFAULT_TEMPLATE_DIR)
    tmpl = env.get_template("set_shell.html.j2")

    payload = [_question_to_payload(q) for q in questions]

    html = tmpl.render(
        student=student,
        template=template,
        questions=questions,
        questions_payload=payload,
        set_id=set_id,
        webhook_url=webhook_url.rstrip("/"),
        webhook_secret=webhook_secret,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path


def _question_to_payload(q: Question) -> dict:
    """Shape sent to the embedded JS. Keeps `html_render` raw so the AI-authored
    stem+choices render exactly as Notion stored them."""
    return {
        "question_id": q.question_id,
        "skill_tag": q.skill_tag,
        "section": q.section,
        "html_render": q.html_render,
        "answer_key": q.answer_key,
        "explanation_html": q.explanation_html,
        "time_target_sec": q.time_target_sec,
    }


def _make_env(template_dir: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
