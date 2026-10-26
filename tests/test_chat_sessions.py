"""
Tests for multi-session requirement chat: POST/GET/DELETE /search/sessions,
POST /search/sessions/{id}/activate, and session_id-scoped /search/plan/chat.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from fastapi.testclient import TestClient
from app.main import app
from app.api import search as search_module
from app.services import knowledge_service

client = TestClient(app)


class _FakeKnowledgeCollection:
    """In-memory double for knowledge_service's Motor collection — avoids
    hitting the real MongoDB configured in .env for this integration test,
    same reasoning as test_knowledge_service.py's FakeCollection."""

    def __init__(self):
        self.docs = {}

    async def insert_one(self, doc):
        from bson import ObjectId
        oid = ObjectId()
        self.docs[str(oid)] = {**doc, "_id": oid}
        return type("R", (), {"inserted_id": oid})()

    def find(self):
        docs = sorted(self.docs.values(), key=lambda d: d["created_at"], reverse=True)

        class _Cursor:
            def sort(self, *a, **k):
                return self

            def limit(self, *a, **k):
                return self

            def __aiter__(self):
                self._it = iter(docs)
                return self

            async def __anext__(self):
                try:
                    return next(self._it)
                except StopIteration:
                    raise StopAsyncIteration

        return _Cursor()

    async def delete_one(self, filter_):
        key = str(filter_["_id"])
        existed = key in self.docs
        self.docs.pop(key, None)
        return type("R", (), {"deleted_count": 1 if existed else 0})()


async def _noop_persist() -> None:
    return None


def _reset_to_one_empty_session():
    store = search_module._session_store
    for sid in list(store.sessions.keys()):
        asyncio.run(store.delete_session(sid, _noop_persist))
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


def test_chat_edit_remembers_a_flagged_fact_and_it_shows_up_in_knowledge_base(monkeypatch):
    """Simulates the LLM flagging a durable rule via generate_chat_reply's
    known_facts/._last_remembered_fact contract (see requirement_agent.py's
    "remember" JSON field) — without a real LLM call, same as the rest of
    this file's rule-based-fallback tests."""
    _reset_to_one_empty_session()
    fake_knowledge_collection = _FakeKnowledgeCollection()
    monkeypatch.setattr(knowledge_service, "get_collection", lambda: fake_knowledge_collection)
    agent = search_module.requirement_service.agent

    from app.schemas.search_plan import SearchPlan

    def fake_generate_chat_reply(current_plan, message, history, preferred_active_in_default, preferred_provider, known_facts=None):
        agent._last_remembered_fact = "Monthly salary x12 = annual CTC"
        return SearchPlan(), "Got it, I'll remember that.", "fake-provider"

    monkeypatch.setattr(agent, "generate_chat_reply", fake_generate_chat_reply)

    res = client.post("/search/plan/chat", json={"message": "From now on, monthly salary x12 = annual CTC"})
    assert res.status_code == 200
    assert res.json()["remembered_fact"] == "Monthly salary x12 = annual CTC"

    listed = client.get("/search/knowledge").json()["facts"]
    assert any(f["text"] == "Monthly salary x12 = annual CTC" for f in listed)
    fact_id = next(f["id"] for f in listed if f["text"] == "Monthly salary x12 = annual CTC")

    deleted = client.delete(f"/search/knowledge/{fact_id}")
    assert deleted.status_code == 200
    assert not any(f["id"] == fact_id for f in client.get("/search/knowledge").json()["facts"])


def test_delete_unknown_knowledge_fact_returns_404():
    res = client.delete("/search/knowledge/000000000000000000000000")
    assert res.status_code == 404


def test_clear_chat_resets_session_in_place_without_removing_it_from_the_list():
    _reset_to_one_empty_session()
    session_id = search_module._session_store.active_session_id
    client.post("/search/plan/chat", json={"message": "Python developer"})

    res = client.delete(f"/search/plan/chat?session_id={session_id}")
    assert res.status_code == 200

    assert search_module._session_store.get(session_id) is not None, "reset must not remove the session from the list"
    assert search_module._session_store.get(session_id)["chat_history"] == []
    assert search_module._session_store.get(session_id)["draft_plan"] is None
