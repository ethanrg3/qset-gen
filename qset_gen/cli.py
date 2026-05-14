"""Typer CLI surface — plan §9 Phase 1.

Commands:
  qset-gen generate --student NAME --template TEMPLATE
  qset-gen ingest-session --transcript PATH --student NAME --session-date YYYY-MM-DD
  qset-gen refresh-cache
  qset-gen webhook
"""

from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path

import typer
from dotenv import load_dotenv

from .adapt.weak_strong import AdaptParams
from .cache import Cache
from .config import load_config
from .models import Attempt, Question, SessionSignals, Student
from .render.render import render_set
from .selection.cold_start import cold_start_weights, diagnostic_template, is_cold_start
from .selection.constraints import sample_set
from .selection.scoring import StudentContext, score
from .selection.templates import load_template
from .session.directives import resolve_directive_skill_ids
from .session.extractor import SessionExtractor
from .session.ingest import ingest_transcript

app = typer.Typer(
    name="qset-gen",
    help="Personalized ACT/SAT homework generator (Notion-backed).",
    no_args_is_help=True,
)

# Load .env on import so subcommands see the secrets.
load_dotenv()


@app.command()
def generate(
    student: str = typer.Option(..., "--student", "-s", help="Student name as it appears in Notion."),
    template: str = typer.Option(..., "--template", "-t", help="Template name (e.g. act_math_mixed_20)."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output HTML path."),
    refresh: bool = typer.Option(False, "--refresh", help="Bypass cache and re-pull from Notion."),
    config_path: Path = typer.Option(Path("config.toml"), "--config", help="Path to config.toml."),
) -> None:
    """Generate a homework set as a single self-contained HTML file.

    Reads from the local SQLite cache (populated by `qset-gen refresh-cache`).
    Runs end-to-end without Notion as long as the cache has been seeded.
    """
    cfg = load_config(config_path)

    if refresh:
        typer.echo("⚠ --refresh requires Notion wiring (NotImplementedError). Skipping for now.", err=True)

    cache = Cache(cfg.paths.cache_db)
    cache.init_schema()

    student_obj = cache.get_student_by_name(student)
    if student_obj is None:
        typer.echo(f"✗ Student '{student}' not found in cache. Run `qset-gen refresh-cache` first.", err=True)
        raise typer.Exit(1)

    questions: list[Question] = cache.get_questions(only_active=True)
    if not questions:
        typer.echo("✗ No questions in cache. Run `qset-gen refresh-cache` first.", err=True)
        raise typer.Exit(1)

    history: list[Attempt] = cache.get_attempts(student_id=student_obj.student_id)
    sessions: list[SessionSignals] = cache.get_session_signals(student_id=student_obj.student_id)
    taxonomy = cache.get_taxonomy()

    template_obj = load_template(template, cfg.paths.templates_dir)

    # Cold-start adjusts weights + diagnostic-leaning template.
    cold = is_cold_start(student_obj, history, sessions)
    weights = cold_start_weights(cfg.weights) if cold else cfg.weights
    template_obj = diagnostic_template(template_obj) if cold else template_obj

    qmap = {q.question_id: q.skill_tag for q in questions}
    latest_session = max(sessions, key=lambda s: s.session_date) if sessions else None
    directive_skill_ids = (
        resolve_directive_skill_ids(latest_session.homework_directives, taxonomy)
        if latest_session else set()
    )

    ctx = StudentContext(
        student=student_obj, history=history, sessions=sessions,
        today=date.today(),
        question_skill_map=qmap, directive_skill_ids=directive_skill_ids,
    )
    ranked = sorted(questions, key=lambda q: score(q, ctx, weights), reverse=True)
    picked = sample_set(ranked, template_obj, ctx)
    if not picked:
        typer.echo("✗ Sampler returned no questions. Check that the candidate pool isn't empty.", err=True)
        raise typer.Exit(1)

    set_id = f"set_{student_obj.student_id}_{date.today().isoformat()}_{template}"
    output_path = output or (cfg.paths.output_dir / f"{set_id}.html")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    webhook_url = cfg.webhook_base_url or "https://webhook-not-configured.example.com"
    webhook_secret = cfg.webhook_secret or "WEBHOOK_SECRET_NOT_SET"
    if not cfg.webhook_base_url or not cfg.webhook_secret:
        typer.echo("⚠ WEBHOOK_BASE_URL or WEBHOOK_SECRET unset — HTML will not submit successfully.", err=True)

    render_set(
        student=student_obj, template=template_obj, questions=picked,
        set_id=set_id, webhook_url=webhook_url, webhook_secret=webhook_secret,
        output_path=output_path,
    )

    cold_tag = " [cold-start diagnostic]" if cold else ""
    typer.echo(f"✓ Generated {set_id}: {len(picked)} questions → {output_path}{cold_tag}")


@app.command(name="ingest-session")
def ingest_session(
    transcript: Path = typer.Option(..., "--transcript", help="Path to Fathom transcript text file."),
    student: str = typer.Option(..., "--student", "-s", help="Student name."),
    session_date: datetime = typer.Option(
        ..., "--session-date", formats=["%Y-%m-%d"], help="Session date (YYYY-MM-DD)."
    ),
    duration_min: int | None = typer.Option(None, "--duration-min", help="Session duration in minutes."),
    config_path: Path = typer.Option(Path("config.toml"), "--config"),
) -> None:
    """Extract pedagogical signals from a Fathom transcript and write them to Notion.

    Requires NOTION_TOKEN and ANTHROPIC_API_KEY in the environment.
    """
    cfg = load_config(config_path)

    if not cfg.anthropic_api_key:
        typer.echo("✗ ANTHROPIC_API_KEY not set (check .env).", err=True)
        raise typer.Exit(1)
    if not cfg.notion_token:
        typer.echo("✗ NOTION_TOKEN not set (check .env).", err=True)
        raise typer.Exit(1)

    if not transcript.exists():
        typer.echo(f"✗ Transcript file not found: {transcript}", err=True)
        raise typer.Exit(1)
    transcript_text = transcript.read_text(encoding="utf-8")

    gateway = _make_live_gateway(cfg)
    student_obj: Student | None = gateway.fetch_student_by_name(student)
    if student_obj is None:
        typer.echo(f"✗ Student '{student}' not found in Notion.", err=True)
        raise typer.Exit(1)

    extractor = SessionExtractor(
        api_key=cfg.anthropic_api_key,
        model=cfg.extractor.model,
        max_tokens=cfg.extractor.max_tokens,
    )

    signals, changes = ingest_transcript(
        transcript=transcript_text,
        student=student_obj,
        session_date=session_date.date(),
        gateway=gateway,
        extractor=extractor,
        adapt_params=cfg.adapt,
        duration_min=duration_min,
        transcript_excerpt_chars=cfg.extractor.transcript_excerpt_chars,
    )

    typer.echo(f"✓ Session signals written: {signals.session_id}")
    if signals.skills_struggled:
        typer.echo(f"  struggled:  {', '.join(signals.skills_struggled)}")
    if signals.skills_introduced:
        typer.echo(f"  introduced: {', '.join(signals.skills_introduced)}")
    if changes:
        typer.echo(f"  weak/strong updates: {len(changes)}")
        for c in changes:
            typer.echo(f"    {c.skill_id}: {c.prior_status} → {c.new_status} (score={c.weakness_score:.2f})")


@app.command(name="refresh-cache")
def refresh_cache(
    config_path: Path = typer.Option(Path("config.toml"), "--config"),
) -> None:
    """Pull a fresh snapshot of all Notion data into the local SQLite cache."""
    cfg = load_config(config_path)
    if not cfg.notion_token:
        typer.echo("✗ NOTION_TOKEN not set (check .env).", err=True)
        raise typer.Exit(1)
    missing = cfg.notion_dbs.missing()
    if missing:
        typer.echo(f"✗ Missing Notion DB IDs in .env: {', '.join(missing)}", err=True)
        raise typer.Exit(1)

    gateway = _make_live_gateway(cfg)
    cache = Cache(cfg.paths.cache_db)
    cache.init_schema()

    typer.echo("Pulling from Notion...")
    cache.put_skill_taxonomy(gateway.fetch_skill_taxonomy())
    cache.put_questions(gateway.fetch_questions(only_active=False))
    cache.put_students(gateway.fetch_students())
    cache.put_attempts(gateway.fetch_q_history())
    cache.put_session_signals(gateway.fetch_session_signals())
    cache.set_meta("last_refresh", datetime.now().isoformat())
    typer.echo("✓ Cache refreshed.")


@app.command()
def webhook(
    host: str = typer.Option("0.0.0.0", "--host"),
    port: int = typer.Option(8787, "--port"),
    reload: bool = typer.Option(False, "--reload"),
) -> None:
    """Run the FastAPI submission webhook locally."""
    import uvicorn

    uvicorn.run("qset_gen.webhook.app:app", host=host, port=port, reload=reload)


# ----- helpers -----

def _make_live_gateway(cfg) -> "NotionGateway":  # noqa: F821 (forward ref via string)
    from .notion_client import NotionGatewayLive

    return NotionGatewayLive(
        token=cfg.notion_token,
        db_questions=cfg.notion_dbs.questions or "",
        db_students=cfg.notion_dbs.students or "",
        db_q_history=cfg.notion_dbs.q_history or "",
        db_session_signals=cfg.notion_dbs.session_signals or "",
        db_skill_taxonomy=cfg.notion_dbs.skill_taxonomy or "",
        db_skill_status_history=cfg.notion_dbs.skill_status_history or "",
    )


if __name__ == "__main__":
    app()
