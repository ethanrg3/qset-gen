"""SQLite cache mirroring Notion. Plan §4.5.

The generator pulls Notion data into qset.db on each run and reads from there.
This module owns the schema, typed put/get helpers, and JSON list-field
serialization. NotionGateway is responsible for talking to Notion; Cache is
the local mirror.

Q-history uses a composite natural key (student_id, question_id, attempted_at)
instead of an autoincrement id, so re-pulling from Notion via INSERT OR IGNORE
is idempotent.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Iterator

from .models import Attempt, Question, SessionSignals, SkillTaxonomyEntry, Student

SCHEMA = """
CREATE TABLE IF NOT EXISTS questions (
    question_id     TEXT PRIMARY KEY,
    test            TEXT NOT NULL,
    section         TEXT NOT NULL,
    skill_tag       TEXT NOT NULL,
    difficulty_low  REAL NOT NULL,
    difficulty_high REAL NOT NULL,
    html_render     TEXT NOT NULL,
    answer_key      TEXT NOT NULL,
    explanation_html TEXT NOT NULL,
    time_target_sec INTEGER NOT NULL,
    active          INTEGER NOT NULL DEFAULT 1,
    fetched_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS students (
    student_id              TEXT PRIMARY KEY,
    name                    TEXT NOT NULL,
    current_act_math        REAL,
    target_act_math         REAL,
    test_date               TEXT,
    weak_skills_json        TEXT NOT NULL DEFAULT '[]',
    strong_skills_json      TEXT NOT NULL DEFAULT '[]',
    last_set_generated_at   TEXT,
    last_session_at         TEXT,
    fetched_at              TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS q_history (
    student_id      TEXT NOT NULL,
    question_id     TEXT NOT NULL,
    attempted_at    TEXT NOT NULL,
    correct         INTEGER NOT NULL,
    time_spent_sec  INTEGER NOT NULL,
    set_id          TEXT NOT NULL,
    confidence      TEXT,
    fetched_at      TEXT NOT NULL,
    PRIMARY KEY (student_id, question_id, attempted_at)
);
CREATE INDEX IF NOT EXISTS idx_qh_student ON q_history(student_id);
CREATE INDEX IF NOT EXISTS idx_qh_question ON q_history(question_id);
CREATE INDEX IF NOT EXISTS idx_qh_attempted ON q_history(attempted_at);

CREATE TABLE IF NOT EXISTS session_signals (
    session_id                 TEXT PRIMARY KEY,
    student_id                 TEXT NOT NULL,
    session_date               TEXT NOT NULL,
    duration_min               INTEGER,
    skills_practiced_json      TEXT NOT NULL DEFAULT '[]',
    skills_struggled_json      TEXT NOT NULL DEFAULT '[]',
    skills_introduced_json     TEXT NOT NULL DEFAULT '[]',
    skills_mastered_today_json TEXT NOT NULL DEFAULT '[]',
    misconceptions_json        TEXT NOT NULL DEFAULT '[]',
    homework_directives_json   TEXT NOT NULL DEFAULT '[]',
    raw_transcript_excerpt     TEXT,
    extraction_model           TEXT,
    fetched_at                 TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ss_student ON session_signals(student_id);
CREATE INDEX IF NOT EXISTS idx_ss_date ON session_signals(session_date);

CREATE TABLE IF NOT EXISTS skill_taxonomy (
    skill_id        TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    description     TEXT,
    fetched_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cache_meta (
    key             TEXT PRIMARY KEY,
    value           TEXT NOT NULL
);
"""


class Cache:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    # ----- writes (typed) -----

    def put_questions(self, questions: list[Question]) -> None:
        now = _utcnow_iso()
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO questions
                (question_id, test, section, skill_tag, difficulty_low, difficulty_high,
                 html_render, answer_key, explanation_html, time_target_sec, active, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (q.question_id, q.test, q.section, q.skill_tag, q.difficulty_low, q.difficulty_high,
                     q.html_render, q.answer_key, q.explanation_html, q.time_target_sec,
                     1 if q.active else 0, now)
                    for q in questions
                ],
            )

    def put_students(self, students: list[Student]) -> None:
        now = _utcnow_iso()
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO students
                (student_id, name, current_act_math, target_act_math, test_date,
                 weak_skills_json, strong_skills_json,
                 last_set_generated_at, last_session_at, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (s.student_id, s.name, s.current_act_math, s.target_act_math,
                     _date_iso(s.test_date),
                     json.dumps(s.weak_skills), json.dumps(s.strong_skills),
                     _datetime_iso(s.last_set_generated_at), _datetime_iso(s.last_session_at), now)
                    for s in students
                ],
            )

    def put_attempts(self, attempts: list[Attempt]) -> None:
        """Idempotent on (student_id, question_id, attempted_at)."""
        now = _utcnow_iso()
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO q_history
                (student_id, question_id, attempted_at, correct, time_spent_sec, set_id, confidence, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (a.student_id, a.question_id, _datetime_iso(a.attempted_at),
                     1 if a.correct else 0, a.time_spent_sec, a.set_id, a.confidence, now)
                    for a in attempts
                ],
            )

    def put_session_signals(self, signals: list[SessionSignals]) -> None:
        now = _utcnow_iso()
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO session_signals
                (session_id, student_id, session_date, duration_min,
                 skills_practiced_json, skills_struggled_json, skills_introduced_json,
                 skills_mastered_today_json, misconceptions_json, homework_directives_json,
                 raw_transcript_excerpt, extraction_model, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (s.session_id, s.student_id, _date_iso(s.session_date), s.duration_min,
                     json.dumps(s.skills_practiced), json.dumps(s.skills_struggled),
                     json.dumps(s.skills_introduced), json.dumps(s.skills_mastered_today),
                     json.dumps(s.misconceptions), json.dumps(s.homework_directives),
                     s.raw_transcript_excerpt, s.extraction_model, now)
                    for s in signals
                ],
            )

    def put_skill_taxonomy(self, entries: list[SkillTaxonomyEntry]) -> None:
        now = _utcnow_iso()
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO skill_taxonomy (skill_id, name, description, fetched_at)
                VALUES (?, ?, ?, ?)
                """,
                [(e.skill_id, e.name, e.description, now) for e in entries],
            )

    # ----- reads (typed) -----

    def get_questions(self, *, only_active: bool = True) -> list[Question]:
        with self.connect() as conn:
            sql = "SELECT * FROM questions"
            if only_active:
                sql += " WHERE active = 1"
            rows = conn.execute(sql).fetchall()
            return [_row_to_question(r) for r in rows]

    def get_student(self, student_id: str) -> Student | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM students WHERE student_id = ?", (student_id,)).fetchone()
            return _row_to_student(row) if row else None

    def get_student_by_name(self, name: str) -> Student | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM students WHERE name = ?", (name,)).fetchone()
            return _row_to_student(row) if row else None

    def get_attempts(self, *, student_id: str | None = None) -> list[Attempt]:
        with self.connect() as conn:
            if student_id:
                rows = conn.execute(
                    "SELECT * FROM q_history WHERE student_id = ? ORDER BY attempted_at DESC", (student_id,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM q_history ORDER BY attempted_at DESC").fetchall()
            return [_row_to_attempt(r) for r in rows]

    def get_session_signals(self, *, student_id: str | None = None) -> list[SessionSignals]:
        with self.connect() as conn:
            if student_id:
                rows = conn.execute(
                    "SELECT * FROM session_signals WHERE student_id = ? ORDER BY session_date DESC",
                    (student_id,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM session_signals ORDER BY session_date DESC").fetchall()
            return [_row_to_session(r) for r in rows]

    def get_taxonomy(self) -> list[SkillTaxonomyEntry]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM skill_taxonomy").fetchall()
            return [SkillTaxonomyEntry(skill_id=r["skill_id"], name=r["name"], description=r["description"])
                    for r in rows]

    # ----- meta -----

    def set_meta(self, key: str, value: str) -> None:
        with self.connect() as conn:
            conn.execute("INSERT OR REPLACE INTO cache_meta (key, value) VALUES (?, ?)", (key, value))

    def get_meta(self, key: str) -> str | None:
        with self.connect() as conn:
            row = conn.execute("SELECT value FROM cache_meta WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else None


# ----- row converters -----

def _row_to_question(r: sqlite3.Row) -> Question:
    return Question(
        question_id=r["question_id"],
        test=r["test"],
        section=r["section"],
        skill_tag=r["skill_tag"],
        difficulty_low=r["difficulty_low"],
        difficulty_high=r["difficulty_high"],
        html_render=r["html_render"],
        answer_key=r["answer_key"],
        explanation_html=r["explanation_html"],
        time_target_sec=r["time_target_sec"],
        active=bool(r["active"]),
    )


def _row_to_student(r: sqlite3.Row) -> Student:
    return Student(
        student_id=r["student_id"],
        name=r["name"],
        current_act_math=r["current_act_math"],
        target_act_math=r["target_act_math"],
        test_date=_parse_date(r["test_date"]),
        weak_skills=json.loads(r["weak_skills_json"] or "[]"),
        strong_skills=json.loads(r["strong_skills_json"] or "[]"),
        last_set_generated_at=_parse_datetime(r["last_set_generated_at"]),
        last_session_at=_parse_datetime(r["last_session_at"]),
    )


def _row_to_attempt(r: sqlite3.Row) -> Attempt:
    return Attempt(
        student_id=r["student_id"],
        question_id=r["question_id"],
        attempted_at=datetime.fromisoformat(r["attempted_at"]),
        correct=bool(r["correct"]),
        time_spent_sec=r["time_spent_sec"],
        set_id=r["set_id"],
        confidence=r["confidence"],
    )


def _row_to_session(r: sqlite3.Row) -> SessionSignals:
    return SessionSignals(
        session_id=r["session_id"],
        student_id=r["student_id"],
        session_date=date.fromisoformat(r["session_date"]),
        duration_min=r["duration_min"],
        skills_practiced=json.loads(r["skills_practiced_json"] or "[]"),
        skills_struggled=json.loads(r["skills_struggled_json"] or "[]"),
        skills_introduced=json.loads(r["skills_introduced_json"] or "[]"),
        skills_mastered_today=json.loads(r["skills_mastered_today_json"] or "[]"),
        misconceptions=json.loads(r["misconceptions_json"] or "[]"),
        homework_directives=json.loads(r["homework_directives_json"] or "[]"),
        raw_transcript_excerpt=r["raw_transcript_excerpt"],
        extraction_model=r["extraction_model"],
    )


# ----- type helpers -----

def _utcnow_iso() -> str:
    return datetime.now().isoformat()


def _date_iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def _datetime_iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _parse_date(s: str | None) -> date | None:
    return date.fromisoformat(s) if s else None


def _parse_datetime(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s else None
