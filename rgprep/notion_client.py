"""Wrapper around the official notion-client SDK.

Read paths: questions, students, q_history, session_signals, skill_taxonomy.
Write paths: q_history rows (per submission), session_signals rows (per session ingest),
student weak/strong updates, skill_status_history append.
"""

from __future__ import annotations

from datetime import date, datetime

from .models import (
    Attempt,
    Question,
    SessionSignals,
    SkillTaxonomyEntry,
    Student,
)


class NotionGateway:
    """All Notion I/O lives behind this class so the rest of the codebase stays test-friendly."""

    def __init__(
        self,
        token: str,
        db_questions: str,
        db_students: str,
        db_q_history: str,
        db_session_signals: str,
        db_skill_taxonomy: str,
        db_skill_status_history: str,
    ) -> None:
        self.token = token
        self.db_questions = db_questions
        self.db_students = db_students
        self.db_q_history = db_q_history
        self.db_session_signals = db_session_signals
        self.db_skill_taxonomy = db_skill_taxonomy
        self.db_skill_status_history = db_skill_status_history

    # ---- reads ----

    def fetch_questions(self, *, only_active: bool = True) -> list[Question]:
        raise NotImplementedError

    def fetch_students(self) -> list[Student]:
        raise NotImplementedError

    def fetch_student_by_name(self, name: str) -> Student | None:
        raise NotImplementedError

    def fetch_q_history(
        self, *, student_id: str | None = None, since: datetime | None = None
    ) -> list[Attempt]:
        raise NotImplementedError

    def fetch_session_signals(
        self, *, student_id: str | None = None, since: date | None = None
    ) -> list[SessionSignals]:
        raise NotImplementedError

    def fetch_skill_taxonomy(self) -> list[SkillTaxonomyEntry]:
        raise NotImplementedError

    # ---- writes ----

    def write_attempts(self, attempts: list[Attempt]) -> None:
        """Plan §8.3 — one Q-History row per attempt."""
        raise NotImplementedError

    def write_session_signals(self, signals: SessionSignals) -> str:
        """Returns the Notion page id of the created row."""
        raise NotImplementedError

    def update_student_skills(
        self, student_id: str, weak_skill_ids: list[str], strong_skill_ids: list[str]
    ) -> None:
        raise NotImplementedError

    def append_skill_status_history(
        self,
        student_id: str,
        skill_id: str,
        prior_status: str,
        new_status: str,
        weakness_score: float,
        triggered_by: str,
    ) -> None:
        """Append-only audit row — plan §9 Phase 3."""
        raise NotImplementedError
