"""
Tests for POST /search/plan/live-keywords — the extension reports keywords
currently live in the Resdex form (including manual HR edits) so the
website's draft keyword section stays in sync. One-way, extension -> backend,
and must never touch _latest_search_plan or trigger a re-apply-to-Resdex
(that's the opposite direction, PATCH /plan/keywords).
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from fastapi.testclient import TestClient
from app.main import app
from app.api import search as search_module

client = TestClient(app)


def _set_draft(keywords=None):
    search_module._draft_plan = {
        "keywords": keywords or {"required": [], "preferred": []},
        "min_experience": None,
    }
    search_module._draft_timestamp = 0.0


def _clear_draft():
    search_module._draft_plan = None
    search_module._draft_timestamp = 0.0


def test_no_draft_yet_is_a_safe_no_op():
    _clear_draft()
    res = client.post("/search/plan/live-keywords", json={"required": ["Python"], "preferred": []})
    assert res.status_code == 200
    body = res.json()
    assert body["synced"] is False
    assert search_module._draft_plan is None  # must not fabricate a draft out of nowhere


def test_updates_existing_draft_keywords():
    _set_draft({"required": ["Java"], "preferred": ["Spring"]})
    res = client.post("/search/plan/live-keywords", json={"required": ["Python", "Django"], "preferred": ["FastAPI"]})
    assert res.status_code == 200
    body = res.json()
    assert body["synced"] is True
    assert search_module._draft_plan["keywords"]["required"] == ["Python", "Django"]
    assert search_module._draft_plan["keywords"]["preferred"] == ["FastAPI"]
    _clear_draft()


def test_no_change_is_not_reported_as_synced():
    _set_draft({"required": ["Python"], "preferred": []})
    res = client.post("/search/plan/live-keywords", json={"required": ["Python"], "preferred": []})
    assert res.status_code == 200
    assert res.json()["synced"] is False
    _clear_draft()


def test_does_not_touch_the_separately_applied_plan():
    """This is the reverse direction of PATCH /plan/keywords — it must never
    write to _latest_search_plan or set _keyword_sync_only/_submit_search,
    or a Resdex-side read would ping-pong into a re-apply loop."""
    _set_draft({"required": ["Old"], "preferred": []})
    search_module._latest_search_plan = {"keywords": {"required": ["Untouched"], "preferred": []}}
    client.post("/search/plan/live-keywords", json={"required": ["New"], "preferred": []})
    assert search_module._latest_search_plan["keywords"]["required"] == ["Untouched"]
    assert "_keyword_sync_only" not in search_module._latest_search_plan
    _clear_draft()
    search_module._latest_search_plan = None


def test_get_plan_chat_reflects_the_synced_draft():
    _set_draft({"required": ["Old"], "preferred": []})
    client.post("/search/plan/live-keywords", json={"required": ["Python", "Go"], "preferred": []})
    res = client.get("/search/plan/chat")
    assert res.status_code == 200
    assert res.json()["plan"]["keywords"]["required"] == ["Python", "Go"]
    _clear_draft()
