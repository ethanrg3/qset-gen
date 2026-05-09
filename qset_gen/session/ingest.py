"""Transcript → Session Signals → recompute. Plan §6.1 (`qset-gen ingest-session`)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from ..models import SessionSignals


def ingest_transcript(
    *,
    transcript_path: Path,
    student_name: str,
    session_date: date,
    duration_min: int | None = None,
) -> SessionSignals:
    """Read transcript → extract → write Session Signals row → trigger weak/strong recompute.

    Returns the SessionSignals object that was written.
    """
    raise NotImplementedError
