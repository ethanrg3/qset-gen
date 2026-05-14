"""FastAPI submission webhook — plan §8.3.

POST /submit
  body: { student_id, set_id, attempts: [{question_id, selected, correct, time_spent_sec}] }
  → writes to Notion Q-History (one row per attempt)
  → triggers adaptive weak/strong recompute
  → returns { ok: true, summary: { score, by_skill, resurface_accuracy } }

The gateway and adapt params come from FastAPI dependencies; tests override
those dependencies with an InMemoryGateway instead of touching Notion.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from ..adapt.weak_strong import AdaptParams, recompute_weak_strong
from ..models import Attempt, SubmitPayload
from ..notion_client import NotionGateway, NotionGatewayLive
from .auth import require_secret
from .summary import build_summary, utc_now

app = FastAPI(title="qset-gen webhook", version="0.1.0")

# Permissive CORS — generated HTML files are opened from disk (Origin: null).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


# ----- dependency-injection seams -----

def get_gateway() -> NotionGateway:
    """Default gateway provider — overridden in tests via app.dependency_overrides.

    Production path constructs a NotionGatewayLive from env vars. Until Notion
    wiring is live, the live gateway's methods raise NotImplementedError, which
    surfaces as a clean 501 here.
    """
    import os

    return NotionGatewayLive(
        token=os.environ.get("NOTION_TOKEN", ""),
        db_questions=os.environ.get("NOTION_DB_QUESTIONS", ""),
        db_students=os.environ.get("NOTION_DB_STUDENTS", ""),
        db_q_history=os.environ.get("NOTION_DB_Q_HISTORY", ""),
        db_session_signals=os.environ.get("NOTION_DB_SESSION_SIGNALS", ""),
        db_skill_taxonomy=os.environ.get("NOTION_DB_SKILL_TAXONOMY", ""),
        db_skill_status_history=os.environ.get("NOTION_DB_SKILL_STATUS_HISTORY", ""),
    )


def get_adapt_params() -> AdaptParams:
    """Default adapt params — overridden in tests if needed."""
    return AdaptParams()


# ----- routes -----

@app.get("/healthz")
async def healthz() -> dict:
    return {"ok": True}


@app.post("/submit", dependencies=[Depends(require_secret)])
async def submit(
    payload: SubmitPayload,
    gateway: NotionGateway = Depends(get_gateway),
    adapt_params: AdaptParams = Depends(get_adapt_params),
) -> dict:
    """Persist attempts, recompute weak/strong, return per-skill summary."""
    student = gateway.fetch_student_by_id(payload.student_id)
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"student '{payload.student_id}' not found",
        )

    # Prior history before persisting these attempts — used for resurface accuracy.
    prior_history: list[Attempt] = gateway.fetch_q_history(student_id=student.student_id)

    # Persist the new attempts (they may already have correct/time set client-side).
    # If the client didn't fill `attempted_at`, the pydantic model already required it,
    # so anything we receive here is valid; we just forward.
    gateway.write_attempts(payload.attempts)

    # Recompute weak/strong with the new attempts in the picture.
    new_history = prior_history + payload.attempts
    sessions = gateway.fetch_session_signals(student_id=student.student_id)
    taxonomy = gateway.fetch_skill_taxonomy()
    questions = gateway.fetch_questions(only_active=False)
    questions_by_id = {q.question_id: q for q in questions}
    qmap = {q.question_id: q.skill_tag for q in questions}

    new_weak, new_strong, changes = recompute_weak_strong(
        student=student,
        history=new_history,
        sessions=sessions,
        taxonomy=taxonomy,
        params=adapt_params,
        question_skill_map=qmap,
        today=utc_now().date(),
    )
    gateway.update_student_skills(student.student_id, new_weak, new_strong)
    for change in changes:
        gateway.append_skill_status_history(
            student_id=student.student_id,
            skill_id=change.skill_id,
            prior_status=change.prior_status,
            new_status=change.new_status,
            weakness_score=change.weakness_score,
            triggered_by=f"webhook/submit/{payload.set_id}",
        )

    summary = build_summary(payload.attempts, questions_by_id, prior_history)
    return {"ok": True, "summary": summary, "changes": [c.__dict__ for c in changes]}


@app.post("/sessions", dependencies=[Depends(require_secret)])
async def sessions_endpoint(payload: dict) -> dict:
    """Optional convenience for later — Fathom auto-trigger (plan §8.3).

    Not implemented in v1; v1 ingests via the `qset-gen ingest-session` CLI.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="POST /sessions not implemented in v1 — use `qset-gen ingest-session` CLI",
    )
