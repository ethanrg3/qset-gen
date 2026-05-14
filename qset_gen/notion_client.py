"""Notion gateway — protocol + live impl + in-memory fake for tests.

`NotionGateway` is a typing.Protocol so the webhook, ingest pipeline, and CLI
depend on the *interface* rather than a concrete class. `NotionGatewayLive` is
the real Notion-backed impl (methods raise NotImplementedError until creds and
DB IDs are wired up — see the README section on Notion setup). `InMemoryGateway`
is a working fake used by tests and by `qset-gen` runs that operate purely
against the local cache.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Protocol, runtime_checkable

from .models import (
    Attempt,
    Question,
    SessionSignals,
    SkillTaxonomyEntry,
    Student,
)


@runtime_checkable
class NotionGateway(Protocol):
    """Structural type for Notion-side I/O. Both NotionGatewayLive and
    InMemoryGateway satisfy this protocol."""

    # ---- reads ----
    def fetch_questions(self, *, only_active: bool = True) -> list[Question]: ...
    def fetch_students(self) -> list[Student]: ...
    def fetch_student_by_id(self, student_id: str) -> Student | None: ...
    def fetch_student_by_name(self, name: str) -> Student | None: ...
    def fetch_q_history(
        self, *, student_id: str | None = None, since: datetime | None = None
    ) -> list[Attempt]: ...
    def fetch_session_signals(
        self, *, student_id: str | None = None, since: date | None = None
    ) -> list[SessionSignals]: ...
    def fetch_skill_taxonomy(self) -> list[SkillTaxonomyEntry]: ...

    # ---- writes ----
    def write_attempts(self, attempts: list[Attempt]) -> None: ...
    def write_session_signals(self, signals: SessionSignals) -> str: ...
    def update_student_skills(
        self, student_id: str, weak_skill_ids: list[str], strong_skill_ids: list[str]
    ) -> None: ...
    def append_skill_status_history(
        self,
        student_id: str,
        skill_id: str,
        prior_status: str,
        new_status: str,
        weakness_score: float,
        triggered_by: str,
    ) -> None: ...


class NotionGatewayLive:
    """Real Notion-backed gateway. NOT YET IMPLEMENTED — methods raise
    NotImplementedError until the user has provisioned the Notion DBs and
    set the corresponding env vars. See README §Notion setup.

    Wiring will live behind these methods; the rest of the codebase stays
    untouched because everyone depends on NotionGateway (the Protocol).
    """

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

    def fetch_questions(self, *, only_active: bool = True) -> list[Question]:
        raise NotImplementedError("NotionGatewayLive.fetch_questions: pending Notion wiring")

    def fetch_students(self) -> list[Student]:
        raise NotImplementedError("NotionGatewayLive.fetch_students: pending Notion wiring")

    def fetch_student_by_id(self, student_id: str) -> Student | None:
        raise NotImplementedError("NotionGatewayLive.fetch_student_by_id: pending Notion wiring")

    def fetch_student_by_name(self, name: str) -> Student | None:
        raise NotImplementedError("NotionGatewayLive.fetch_student_by_name: pending Notion wiring")

    def fetch_q_history(self, *, student_id=None, since=None) -> list[Attempt]:
        raise NotImplementedError("NotionGatewayLive.fetch_q_history: pending Notion wiring")

    def fetch_session_signals(self, *, student_id=None, since=None) -> list[SessionSignals]:
        raise NotImplementedError("NotionGatewayLive.fetch_session_signals: pending Notion wiring")

    def fetch_skill_taxonomy(self) -> list[SkillTaxonomyEntry]:
        raise NotImplementedError("NotionGatewayLive.fetch_skill_taxonomy: pending Notion wiring")

    def write_attempts(self, attempts: list[Attempt]) -> None:
        raise NotImplementedError("NotionGatewayLive.write_attempts: pending Notion wiring")

    def write_session_signals(self, signals: SessionSignals) -> str:
        raise NotImplementedError("NotionGatewayLive.write_session_signals: pending Notion wiring")

    def update_student_skills(self, student_id, weak_skill_ids, strong_skill_ids) -> None:
        raise NotImplementedError("NotionGatewayLive.update_student_skills: pending Notion wiring")

    def append_skill_status_history(self, *args, **kwargs) -> None:
        raise NotImplementedError("NotionGatewayLive.append_skill_status_history: pending Notion wiring")


class InMemoryGateway:
    """A working gateway backed by Python dicts/lists. Used by tests and by
    `qset-gen` runs that don't need Notion yet (e.g. local-cache-only mode).

    Seeds: pass `questions`, `students`, etc. at construction time to mimic
    the state of the Notion DBs.
    """

    def __init__(
        self,
        *,
        questions: list[Question] | None = None,
        students: list[Student] | None = None,
        q_history: list[Attempt] | None = None,
        session_signals: list[SessionSignals] | None = None,
        skill_taxonomy: list[SkillTaxonomyEntry] | None = None,
    ) -> None:
        self._questions: dict[str, Question] = {q.question_id: q for q in (questions or [])}
        self._students: dict[str, Student] = {s.student_id: s for s in (students or [])}
        self._q_history: list[Attempt] = list(q_history or [])
        self._session_signals: dict[str, SessionSignals] = {
            s.session_id: s for s in (session_signals or [])
        }
        self._taxonomy: list[SkillTaxonomyEntry] = list(skill_taxonomy or [])
        self.skill_status_log: list[dict] = []  # exposed for test assertions

    # ---- reads ----

    def fetch_questions(self, *, only_active: bool = True) -> list[Question]:
        qs = list(self._questions.values())
        return [q for q in qs if q.active] if only_active else qs

    def fetch_students(self) -> list[Student]:
        return list(self._students.values())

    def fetch_student_by_id(self, student_id: str) -> Student | None:
        return self._students.get(student_id)

    def fetch_student_by_name(self, name: str) -> Student | None:
        for s in self._students.values():
            if s.name == name:
                return s
        return None

    def fetch_q_history(
        self, *, student_id: str | None = None, since: datetime | None = None
    ) -> list[Attempt]:
        rows = self._q_history
        if student_id is not None:
            rows = [a for a in rows if a.student_id == student_id]
        if since is not None:
            rows = [a for a in rows if a.attempted_at >= since]
        return sorted(rows, key=lambda a: a.attempted_at, reverse=True)

    def fetch_session_signals(
        self, *, student_id: str | None = None, since: date | None = None
    ) -> list[SessionSignals]:
        rows = list(self._session_signals.values())
        if student_id is not None:
            rows = [s for s in rows if s.student_id == student_id]
        if since is not None:
            rows = [s for s in rows if s.session_date >= since]
        return sorted(rows, key=lambda s: s.session_date, reverse=True)

    def fetch_skill_taxonomy(self) -> list[SkillTaxonomyEntry]:
        return list(self._taxonomy)

    # ---- writes ----

    def write_attempts(self, attempts: list[Attempt]) -> None:
        self._q_history.extend(attempts)

    def write_session_signals(self, signals: SessionSignals) -> str:
        self._session_signals[signals.session_id] = signals
        return f"fake_page_{uuid.uuid4().hex[:8]}"

    def update_student_skills(
        self, student_id: str, weak_skill_ids: list[str], strong_skill_ids: list[str]
    ) -> None:
        s = self._students.get(student_id)
        if s is None:
            return
        self._students[student_id] = s.model_copy(
            update={"weak_skills": list(weak_skill_ids), "strong_skills": list(strong_skill_ids)}
        )

    def append_skill_status_history(
        self,
        student_id: str,
        skill_id: str,
        prior_status: str,
        new_status: str,
        weakness_score: float,
        triggered_by: str,
    ) -> None:
        self.skill_status_log.append({
            "student_id": student_id,
            "skill_id": skill_id,
            "prior_status": prior_status,
            "new_status": new_status,
            "weakness_score": weakness_score,
            "triggered_by": triggered_by,
            "logged_at": datetime.now().isoformat(),
        })
