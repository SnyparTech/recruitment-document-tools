"""
Tests for the /search/preferences endpoints and POST /search/plan recording
an active_in-widening observation when a session_id is supplied. Mongo isn't
running in this test environment — preference_service's short-timeout client
fails fast and these calls degrade to their safe empty/no-op results, which
is exactly the behavior being verified (the endpoints must never 500 or
block just because Mongo is unreachable).
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_pending_preference_endpoint_returns_null_when_none_pending():
    res = client.get("/search/preferences/pending")
    assert res.status_code == 200
    assert res.json()["suggestion"] is None


def test_confirm_unknown_pattern_returns_404():
    res = client.post("/search/preferences/does-not-exist/confirm")
    assert res.status_code == 404


def test_reject_unknown_pattern_returns_404():
    res = client.post("/search/preferences/does-not-exist/reject")
    assert res.status_code == 404


def test_apply_plan_with_session_id_does_not_break_when_mongo_unreachable():
    """The actual point of this test: a Mongo hiccup during preference
    recording must never prevent the plan from being applied."""
    payload = {
        "plan": {"keywords": {"required": ["Python"], "preferred": []}, "active_in": "30 days"},
        "submit_search": False,
        "session_id": "some-session-id-that-may-not-exist",
    }
    res = client.post("/search/plan", json=payload)
    assert res.status_code == 200, res.text


def test_apply_plan_without_session_id_still_works():
    payload = {
        "plan": {"keywords": {"required": ["Python"], "preferred": []}},
        "submit_search": False,
    }
    res = client.post("/search/plan", json=payload)
    assert res.status_code == 200, res.text
