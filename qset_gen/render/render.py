"""HTML renderer — plan §8.1, §8.2.

Produces a single self-contained HTML file: question payload, choice handlers,
timer, navigation, results screen — all inlined. Vanilla JS, no build step.
The student opens it in a browser, works through it, and clicks Submit, which
POSTs to the FastAPI webhook URL baked in at render time.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..models import Question, SetTemplate, Student


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
    """Render the question set to a self-contained HTML file. Returns output_path."""
    raise NotImplementedError


def _make_env(template_dir: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
