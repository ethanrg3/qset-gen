"""SQLite cache mirroring Notion. Plan §4.5.

The generator pulls Notion data into rgprep.db on each run and reads from there.
TTL-based; force refresh with --refresh.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

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
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT NOT NULL,
    question_id     TEXT NOT NULL,
    attempted_at    TEXT NOT NULL,
    correct         INTEGER NOT NULL,
    time_spent_sec  INTEGER NOT NULL,
    set_id          TEXT NOT NULL,
    confidence      TEXT,
    fetched_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_qh_student ON q_history(student_id);
CREATE INDEX IF NOT EXISTS idx_qh_question ON q_history(question_id);
CREATE INDEX IF NOT EXISTS idx_qh_attempted ON q_history(attempted_at);

CREATE TABLE IF NOT EXISTS session_signals (
    session_id              TEXT PRIMARY KEY,
    student_id              TEXT NOT NULL,
    session_date            TEXT NOT NULL,
    duration_min            INTEGER,
    skills_practiced_json   TEXT NOT NULL DEFAULT '[]',
    skills_struggled_json   TEXT NOT NULL DEFAULT '[]',
    skills_introduced_json  TEXT NOT NULL DEFAULT '[]',
    skills_mastered_today_json TEXT NOT NULL DEFAULT '[]',
    misconceptions_json     TEXT NOT NULL DEFAULT '[]',
    homework_directives_json TEXT NOT NULL DEFAULT '[]',
    raw_transcript_excerpt  TEXT,
    extraction_model        TEXT,
    fetched_at              TEXT NOT NULL
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

    def upsert_questions(self, rows: list[dict]) -> None:
        raise NotImplementedError

    def upsert_students(self, rows: list[dict]) -> None:
        raise NotImplementedError

    def upsert_q_history(self, rows: list[dict]) -> None:
        raise NotImplementedError

    def upsert_session_signals(self, rows: list[dict]) -> None:
        raise NotImplementedError

    def upsert_skill_taxonomy(self, rows: list[dict]) -> None:
        raise NotImplementedError
