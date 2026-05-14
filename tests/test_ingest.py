"""Session ingest pipeline tests (plan §6.1) with fake gateway + extractor."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from qset_gen.models import (
    Attempt,
    Question,
    SessionSignals,
    SkillTaxonomyEntry,
    Student,
)
from qset_gen.notion_client import InMemoryGateway
from qset_gen.session.extractor import SessionExtractor
from qset_gen.session.ingest import ingest_transcript


@dataclass
class _Block:
    text: str


@dataclass
class _Response:
    content: list[_Block]


class _FakeMessages:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def create(self, **kwargs) -> _Response:
        return _Response(content=[_Block(text=json.dumps(self.payload))])


class _FakeClient:
    def __init__(self, payload: dict) -> None:
        self.messages = _FakeMessages(payload)


def _gateway() -> InMemoryGateway:
    return InMemoryGateway(
        questions=[
            Question(question_id="Q1", test="ACT", section="Math", skill_tag="geo",
                     difficulty_low=22, difficulty_high=24,
                     html_render="x", answer_key="A", explanation_html="y"),
        ],
        students=[Student(student_id="stu_hank", name="Hank",
                          current_act_math=24, target_act_math=30,
                          weak_skills=[], strong_skills=[])],
        skill_taxonomy=[
            SkillTaxonomyEntry(skill_id="geo", name="Geometry"),
            SkillTaxonomyEntry(skill_id="alg", name="Algebra"),
        ],
    )


def _extractor(payload: dict) -> SessionExtractor:
    return SessionExtractor(model="claude-opus-4-7", client=_FakeClient(payload))


def test_ingest_writes_session_signals_row():
    gw = _gateway()
    ext = _extractor({
        "skills_practiced": ["geo"], "skills_struggled": ["geo"],
        "skills_introduced": [], "skills_mastered_today": [],
        "misconceptions": [], "homework_directives": [],
    })
    student = gw.fetch_student_by_id("stu_hank")

    signals, changes = ingest_transcript(
        transcript="transcript text",
        student=student,
        session_date=date.today(),
        gateway=gw,
        extractor=ext,
    )
    assert isinstance(signals, SessionSignals)
    assert signals.skills_struggled == ["geo"]
    # Persisted to gateway
    stored = gw.fetch_session_signals(student_id="stu_hank")
    assert len(stored) == 1
    assert stored[0].session_id == signals.session_id


def test_ingest_truncates_transcript_excerpt():
    gw = _gateway()
    ext = _extractor({"skills_practiced": [], "skills_struggled": [], "skills_introduced": [],
                      "skills_mastered_today": [], "misconceptions": [], "homework_directives": []})
    student = gw.fetch_student_by_id("stu_hank")

    long_transcript = "x" * 10000
    signals, _ = ingest_transcript(
        transcript=long_transcript, student=student, session_date=date.today(),
        gateway=gw, extractor=ext, transcript_excerpt_chars=500,
    )
    assert signals.raw_transcript_excerpt is not None
    assert len(signals.raw_transcript_excerpt) == 500


def test_ingest_triggers_weak_strong_recompute():
    """Many prior misses on geo + struggled session → geo promoted to weak."""
    gw = _gateway()
    # Seed prior misses on geo
    for i in range(7):
        gw._q_history.append(Attempt(
            student_id="stu_hank", question_id="Q1",
            attempted_at=datetime.now() - timedelta(days=i),
            correct=False, time_spent_sec=30, set_id="prior",
        ))
    ext = _extractor({
        "skills_practiced": [], "skills_struggled": ["geo"],
        "skills_introduced": [], "skills_mastered_today": [],
        "misconceptions": [], "homework_directives": [],
    })
    student = gw.fetch_student_by_id("stu_hank")

    _, changes = ingest_transcript(
        transcript="transcript", student=student, session_date=date.today(),
        gateway=gw, extractor=ext,
    )
    updated = gw.fetch_student_by_id("stu_hank")
    assert "geo" in updated.weak_skills
    # The change should be in the returned audit list.
    assert any(c.skill_id == "geo" and c.new_status == "weak" for c in changes)


def test_ingest_records_extraction_model_on_signals():
    gw = _gateway()
    ext = _extractor({"skills_practiced": [], "skills_struggled": [], "skills_introduced": [],
                      "skills_mastered_today": [], "misconceptions": [], "homework_directives": []})
    student = gw.fetch_student_by_id("stu_hank")
    signals, _ = ingest_transcript(
        transcript="x", student=student, session_date=date.today(),
        gateway=gw, extractor=ext,
    )
    assert signals.extraction_model == "claude-opus-4-7"
