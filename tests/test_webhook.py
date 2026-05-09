"""Plan §11. POST writes Q-History rows and triggers recompute."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("WEBHOOK_SECRET", "test-secret")
    from rgprep.webhook.app import app

    return TestClient(app)


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_submit_requires_bearer_token(client):
    r = client.post("/submit", json={"student_id": "x", "set_id": "y", "attempts": []})
    assert r.status_code == 401


def test_submit_rejects_wrong_token(client):
    r = client.post(
        "/submit",
        json={"student_id": "x", "set_id": "y", "attempts": []},
        headers={"Authorization": "Bearer wrong"},
    )
    assert r.status_code == 401


@pytest.mark.skip(reason="submit handler not yet implemented (Phase 1)")
def test_submit_writes_q_history():
    pass
