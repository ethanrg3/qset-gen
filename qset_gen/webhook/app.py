"""FastAPI submission webhook — plan §8.3.

POST /submit
  body: { student_id, set_id, attempts: [{question_id, selected, correct, time_spent_sec}] }
  → writes to Notion Q-History (one row per attempt)
  → triggers adaptive weak/strong recompute
  → returns { ok: true, summary: { score, by_skill, resurface_accuracy } }

POST /sessions   (optional convenience for later)
  body: { student_id, session_date, transcript }
  → runs the same path as `qset-gen ingest-session`
"""

from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from ..models import SubmitPayload
from .auth import require_secret

app = FastAPI(title="qset-gen webhook", version="0.1.0")

# Permissive CORS — generated HTML files are opened from disk (Origin: null).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz() -> dict:
    return {"ok": True}


@app.post("/submit", dependencies=[Depends(require_secret)])
async def submit(payload: SubmitPayload) -> dict:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="submit handler not yet implemented (Phase 1)",
    )


@app.post("/sessions", dependencies=[Depends(require_secret)])
async def sessions(payload: dict) -> dict:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="sessions handler not yet implemented (Phase 1)",
    )
