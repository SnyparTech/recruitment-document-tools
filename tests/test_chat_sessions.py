"""
Tests for multi-session requirement chat: POST/GET/DELETE /search/sessions,
POST /search/sessions/{id}/activate, and session_id-scoped /search/plan/chat.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from fastapi.testclient import TestClient
from app.main import app
from app.api import search as search_module

client = TestClient(app)


def _reset_to_one_empty_session():
    store = search_module._session_store
    for sid in list(store.sessions.keys()):
        store.delete_session(sid, lambda: None)
    # delete_session always leaves at least one empty session behind.


def test_create_session_becomes_active_and_appears_in_list():
    _reset_to_one_empty_session()
    before = search_module._session_store.active_session_id

    res = client.post("/search/sessions")
    assert res.status_code == 200
    new_id = res.json()["session"]["id"]
    assert new_id != before
    assert search_module._session_store.active_session_id == new_id

    listed = client.get("/search/sessions").json()["sessions"]
    assert any(s["id"] == new_id and s["active"] for s in listed)


def test_chat_edit_without_session_id_targets_the_active_session():
    _reset_to_one_empty_session()
    active_id = search_module._session_store.active_session_id

    res = client.post("/search/plan/chat", json={"message": "Python developer in Bengaluru"})
    assert res.status_code == 200
    assert res.json()["session_id"] == active_id


def test_two_sessions_keep_independent_chat_history():
    _reset_to_one_empty_session()
    session_a = search_module._session_store.active_session_id

    client.post("/search/plan/chat", json={"message": "Java developer"})

    session_b = client.post("/search/sessions").json()["session"]["id"]
    client.post("/search/plan/chat", json={"message": "Python developer"})

    history_a = client.get(f"/search/plan/chat?session_id={session_a}").json()["history"]
    history_b = client.get(f"/search/plan/chat?session_id={session_b}").json()["history"]

    assert history_a[0]["content"] == "Java developer"
    assert history_b[0]["content"] == "Python developer"


def test_activate_switches_active_session():
    _reset_to_one_empty_session()
    session_a = search_module._session_store.active_session_id
    session_b = client.post("/search/sessions").json()["session"]["id"]
    assert search_module._session_store.active_session_id == session_b

    res = client.post(f"/search/sessions/{session_a}/activate")
    assert res.status_code == 200
    assert search_module._session_store.active_session_id == session_a


def test_activate_unknown_session_returns_404():
    res = client.post("/search/sessions/does-not-exist/activate")
    assert res.status_code == 404


def test_delete_session_falls_back_to_another_session():
    _reset_to_one_empty_session()
    session_a = search_module._session_store.active_session_id
    session_b = client.post("/search/sessions").json()["session"]["id"]
    client.post(f"/search/sessions/{session_a}/activate")

    res = client.delete(f"/search/sessions/{session_a}")
    assert res.status_code == 200
    assert search_module._session_store.active_session_id != session_a
    assert search_module._session_store.get(session_a) is None


def test_deleting_the_only_session_leaves_a_fresh_empty_one():
    _reset_to_one_empty_session()
    only_id = search_module._session_store.active_session_id

    client.delete(f"/search/sessions/{only_id}")

    assert len(search_module._session_store.sessions) == 1
    assert search_module._session_store.active_session_id != only_id


def test_clear_chat_resets_session_in_place_without_removing_it_from_the_list():
    _reset_to_one_empty_session()
    session_id = search_module._session_store.active_session_id
    client.post("/search/plan/chat", json={"message": "Python developer"})

    res = client.delete(f"/search/plan/chat?session_id={session_id}")
    assert res.status_code == 200

    assert search_module._session_store.get(session_id) is not None, "reset must not remove the session from the list"
    assert search_module._session_store.get(session_id)["chat_history"] == []
    assert search_module._session_store.get(session_id)["draft_plan"] is None
