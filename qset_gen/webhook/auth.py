"""Shared-secret auth for the submission webhook — plan §8.3.

The secret is baked into each generated HTML at render time. The HTML POSTs with
`Authorization: Bearer <secret>`; this middleware checks it.
"""

from __future__ import annotations

import hmac
import os

from fastapi import Header, HTTPException, status


def get_webhook_secret() -> str:
    secret = os.environ.get("WEBHOOK_SECRET")
    if not secret:
        raise RuntimeError("WEBHOOK_SECRET is not set")
    return secret


async def require_secret(authorization: str | None = Header(default=None)) -> None:
    """FastAPI dependency. Use with `Depends(require_secret)` on protected routes."""
    expected = get_webhook_secret()
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    presented = authorization.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(presented, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")
