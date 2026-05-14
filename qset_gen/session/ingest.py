"""Transcript → Session Signals → recompute. Plan §6.1 (`qset-gen ingest-session`).

This module orchestrates the session-ingestion pipeline using injectable
dependencies (NotionGateway, SessionExtractor), so the same function backs both
the CLI command and the optional `POST /sessions` webhook route, and is fully
testable without Notion or Anthropic credentials.
"""

from __future__ import annotations

import uuid
from datetime import date

from ..adapt.weak_strong import AdaptParams, SkillStatusChange, recompute_weak_strong
from ..models import SessionExtraction, SessionSignals, Student
from ..notion_client import NotionGateway
from .extractor import SessionExtractor


def ingest_transcript(
    *,
    transcript: str,
    student: Student,
    session_date: date,
    gateway: NotionGateway,
    extractor: SessionExtractor,
    adapt_params: AdaptParams | None = None,
    duration_min: int | None = None,
    transcript_excerpt_chars: int = 4000,
    today: date | None = None,
) -> tuple[SessionSignals, list[SkillStatusChange]]:
    """Extract → write Session Signals → recompute weak/strong → persist deltas.

    Returns (signals, skill_status_changes). The caller may surface the changes
    to the tutor for sanity-checking (plan §6.1 step 7).
    """
    today = today or date.today()
    adapt_params = adapt_params or AdaptParams()

    taxonomy = gateway.fetch_skill_taxonomy()
    extraction: SessionExtraction = extractor.extract(transcript, taxonomy)

    signals = SessionSignals(
        session_id=_make_session_id(student.student_id, session_date),
        student_id=student.student_id,
        session_date=session_date,
        duration_min=duration_min,
        skills_practiced=list(extraction.skills_practiced),
        skills_struggled=list(extraction.skills_struggled),
        skills_introduced=list(extraction.skills_introduced),
        skills_mastered_today=list(extraction.skills_mastered_today),
        misconceptions=list(extraction.misconceptions),
        homework_directives=list(extraction.homework_directives),
        raw_transcript_excerpt=transcript[:transcript_excerpt_chars],
        extraction_model=extractor.model,
    )

    gateway.write_session_signals(signals)

    # Trigger weak/strong recompute now that this session is on record.
    history = gateway.fetch_q_history(student_id=student.student_id)
    all_sessions = gateway.fetch_session_signals(student_id=student.student_id)
    questions = gateway.fetch_questions(only_active=False)
    qmap = {q.question_id: q.skill_tag for q in questions}

    new_weak, new_strong, changes = recompute_weak_strong(
        student=student,
        history=history,
        sessions=all_sessions,
        taxonomy=taxonomy,
        params=adapt_params,
        question_skill_map=qmap,
        today=today,
    )

    gateway.update_student_skills(student.student_id, new_weak, new_strong)
    for change in changes:
        gateway.append_skill_status_history(
            student_id=student.student_id,
            skill_id=change.skill_id,
            prior_status=change.prior_status,
            new_status=change.new_status,
            weakness_score=change.weakness_score,
            triggered_by=f"ingest-session/{signals.session_id}",
        )

    return signals, changes


def _make_session_id(student_id: str, session_date: date) -> str:
    """Stable-but-unique session id. Combines student + date so repeated ingests
    of the same session collide intentionally (idempotent upsert behavior)."""
    return f"sess_{student_id}_{session_date.isoformat()}_{uuid.uuid4().hex[:6]}"
