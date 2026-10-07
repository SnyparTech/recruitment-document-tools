"""
Tests for POST /search/plan/broaden — the "not satisfied with results"
one-click retry (demotes one required keyword to preferred, widens active_in
up to 30 days, flags the plan so the extension re-applies both on Resdex).
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _store_plan(keywords, active_in=None):
    payload = {
        "plan": {"keywords": keywords, **({"active_in": active_in} if active_in else {})},
        "submit_search": False,
    }
    res = client.post("/search/plan", json=payload)
    assert res.status_code == 200, res.text
    return res.json()["search_plan"]


def test_broaden_demotes_keyword_and_widens_active_in_then_flags_for_extension():
    _store_plan({"required": ["Python", "Django", "AWS"], "preferred": []}, active_in="7 days")

    res = client.post("/search/plan/broaden")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "success"
    assert body["plan"]["keywords"]["required"] == ["Python", "Django"]
    assert "AWS" in body["plan"]["keywords"]["preferred"]
    assert body["plan"]["active_in"] == "30 days"
    assert body["plan"]["_submit_search"] is True
    assert body["plan"]["_broaden_search"] is True


def test_broaden_returns_no_change_when_already_maximally_broad():
    _store_plan({"required": ["Python"], "preferred": []}, active_in="30 days")

    res = client.post("/search/plan/broaden")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "no_change"


def test_broaden_endpoint_has_no_device_lock_dependency():
    """This is called by the frontend dashboard, not the extension — must not
    require X-Device-Id (unlike the 3 extension-facing endpoints)."""
    _store_plan({"required": ["Python", "Java"], "preferred": []}, active_in="7 days")
    res = client.post("/search/plan/broaden")  # deliberately no X-Device-Id header
    assert res.status_code != 403
