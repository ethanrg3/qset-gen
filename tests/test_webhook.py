"""Plan §11 / §8.3. Webhook integration tests using InMemoryGateway."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from qset_gen.models import Attempt, Question, SessionSignals, SkillTaxonomyEntry, Student
from qset_gen.notion_client import InMemoryGateway
from qset_gen.webhook.app import app, get_gateway

TODAY = date.today()


def _q(qid: str, skill: str) -> Question:
    return Question(
        question_id=qid, test="ACT", section="Math", skill_tag=skill,
        difficulty_low=22, difficulty_high=24,
        html_render="<p>q</p>", answer_key="A", explanation_html="<p>e</p>",
    )


@pytest.fixture
def seeded_gateway() -> InMemoryGateway:
    return InMemoryGateway(
        questions=[_q("Q1", "geo"), _q("Q2", "alg"), _q("Q3", "geo")],
        students=[Student(student_id="stu_hank", name="Hank",
                          current_act_math=24, target_act_math=30,
                          weak_skills=[], strong_skills=[])],
        skill_taxonomy=[SkillTaxonomyEntry(skill_id="geo", name="Geometry"),
                        SkillTaxonomyEntry(skill_id="alg", name="Algebra")],
    )


@pytest.fixture
def client(monkeypatch, seeded_gateway):
    monkeypatch.setenv("WEBHOOK_SECRET", "test-secret")
    app.dependency_overrides[get_gateway] = lambda: seeded_gateway
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _auth():
    return {"Authorization": "Bearer test-secret"}


def _make_payload(student_id="stu_hank", set_id="set_x", attempts=None):
    if attempts is None:
        attempts = [
            {
                "student_id": student_id,
                "question_id": "Q1",
                "attempted_at": datetime.now().isoformat(),
                "correct": True,
                "time_spent_sec": 45,
                "set_id": set_id,
            },
            {
                "student_id": student_id,
                "question_id": "Q2",
                "attempted_at": datetime.now().isoformat(),
                "correct": False,
                "time_spent_sec": 60,
                "set_id": set_id,
            },
        ]
    return {"student_id": student_id, "set_id": set_id, "attempts": attempts}


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_submit_requires_bearer_token(client):
    r = client.post("/submit", json=_make_payload())
    assert r.status_code == 401


def test_submit_rejects_wrong_token(client):
    r = client.post("/submit", json=_make_payload(), headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401


def test_submit_writes_q_history(client, seeded_gateway):
    r = client.post("/submit", json=_make_payload(), headers=_auth())
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    summary = body["summary"]
    assert summary["score"]["correct"] == 1
    assert summary["score"]["total"] == 2
    # Verify gateway side-effects:
    history = seeded_gateway.fetch_q_history(student_id="stu_hank")
    assert len(history) == 2


def test_submit_unknown_student_returns_404(client):
    payload = _make_payload(student_id="stu_nonexistent")
    r = client.post("/submit", json=payload, headers=_auth())
    assert r.status_code == 404


def test_submit_summary_groups_by_skill(client):
    r = client.post("/submit", json=_make_payload(), headers=_auth())
    summary = r.json()["summary"]
    assert "geo" in summary["by_skill"]
    assert "alg" in summary["by_skill"]
    assert summary["by_skill"]["geo"] == {"correct": 1, "total": 1}
    assert summary["by_skill"]["alg"] == {"correct": 0, "total": 1}


def test_submit_resurface_accuracy_reflects_prior_misses(client, seeded_gateway):
    # Pre-load a miss on Q1 to mark it as "resurfaced".
    seeded_gateway._q_history.append(Attempt(
        student_id="stu_hank", question_id="Q1",
        attempted_at=datetime.now() - timedelta(days=3),
        correct=False, time_spent_sec=30, set_id="prior",
    ))
    r = client.post("/submit", json=_make_payload(), headers=_auth())
    summary = r.json()["summary"]
    assert summary["resurface_accuracy"] is not None
    assert summary["resurface_accuracy"]["total"] == 1  # Q1 only
    assert summary["resurface_accuracy"]["correct"] == 1  # student got it right


def test_submit_triggers_weak_strong_recompute(client, seeded_gateway):
    """After repeated misses on geo questions + a session where geo was struggled,
    the post-submit recompute should mark geo as weak."""
    # Pre-load 7 misses on geo questions.
    for i in range(7):
        seeded_gateway._q_history.append(Attempt(
            student_id="stu_hank", question_id="Q1" if i % 2 == 0 else "Q3",
            attempted_at=datetime.now() - timedelta(days=i),
            correct=False, time_spent_sec=30, set_id="prior",
        ))
    # Plus a recent session where geo was a struggle (adds to weakness_score via β).
    seeded_gateway._session_signals["s_struggle"] = SessionSignals(
        session_id="s_struggle",
        student_id="stu_hank",
        session_date=date.today() - timedelta(days=1),
        skills_struggled=["geo"],
    )

    r = client.post("/submit", json=_make_payload(), headers=_auth())
    assert r.status_code == 200
    updated = seeded_gateway.fetch_student_by_id("stu_hank")
    assert "geo" in updated.weak_skills
    # The skill_status_history append-only log should have a row for the transition.
    geo_log = [r for r in seeded_gateway.skill_status_log if r["skill_id"] == "geo"]
    assert geo_log and geo_log[-1]["new_status"] == "weak"
