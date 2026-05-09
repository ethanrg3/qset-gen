"""Typer CLI surface — plan §9 Phase 1.

Commands:
  rgprep generate --student NAME --template TEMPLATE
  rgprep ingest-session --transcript PATH --student NAME --session-date YYYY-MM-DD
  rgprep refresh-cache
  rgprep webhook
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import typer

app = typer.Typer(
    name="rgprep",
    help="Personalized ACT/SAT homework generator (Notion-backed).",
    no_args_is_help=True,
)


@app.command()
def generate(
    student: str = typer.Option(..., "--student", "-s", help="Student name as it appears in Notion."),
    template: str = typer.Option(..., "--template", "-t", help="Template name (e.g. act_math_mixed_20)."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output HTML path."),
    refresh: bool = typer.Option(False, "--refresh", help="Bypass cache and re-pull from Notion."),
) -> None:
    """Generate a homework set as a single self-contained HTML file."""
    raise NotImplementedError("generate: not yet implemented (Phase 1)")


@app.command(name="ingest-session")
def ingest_session(
    transcript: Path = typer.Option(..., "--transcript", help="Path to Fathom transcript text file."),
    student: str = typer.Option(..., "--student", "-s", help="Student name."),
    session_date: date = typer.Option(..., "--session-date", help="Session date (YYYY-MM-DD)."),
) -> None:
    """Extract pedagogical signals from a Fathom transcript and write them to Notion."""
    raise NotImplementedError("ingest-session: not yet implemented (Phase 1)")


@app.command(name="refresh-cache")
def refresh_cache() -> None:
    """Pull a fresh snapshot of all Notion data into the local SQLite cache."""
    raise NotImplementedError("refresh-cache: not yet implemented (Phase 1)")


@app.command()
def webhook(
    host: str = typer.Option("0.0.0.0", "--host"),
    port: int = typer.Option(8787, "--port"),
    reload: bool = typer.Option(False, "--reload"),
) -> None:
    """Run the FastAPI submission webhook locally."""
    import uvicorn

    uvicorn.run("rgprep.webhook.app:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
