"""
Tests for knowledge_service.py — the cross-session "remembered facts" store
(a salary-conversion formula, a standing exclusion rule, etc. stated mid-chat
and meant to apply to every FUTURE chat, not just the session it was said
in). Uses a small fake Motor-collection double, same pattern as
test_preference_service.py — no real MongoDB needed.
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import pytest
from bson import ObjectId

from app.services import knowledge_service


class _FakeInsertResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class _FakeDeleteResult:
    def __init__(self, deleted_count):
        self.deleted_count = deleted_count


class _FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def __aiter__(self):
        self._iter = iter(self._docs)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


class FakeCollection:
    def __init__(self):
        self.docs = {}  # str(_id) -> doc

    async def insert_one(self, doc):
        oid = ObjectId()
        doc = {**doc, "_id": oid}
        self.docs[str(oid)] = doc
        return _FakeInsertResult(oid)

    def find(self):
        return _FakeCursor(sorted(self.docs.values(), key=lambda d: d["created_at"], reverse=True))

    async def delete_one(self, filter_):
        key = str(filter_["_id"])
        if key in self.docs:
            del self.docs[key]
            return _FakeDeleteResult(1)
        return _FakeDeleteResult(0)


@pytest.fixture
def fake_collection():
    return FakeCollection()


@pytest.mark.asyncio
async def test_add_fact_stores_and_returns_it(fake_collection):
    saved = await knowledge_service.add_fact("Monthly salary x12 = annual CTC", session_id="s1", collection=fake_collection)
    assert saved["text"] == "Monthly salary x12 = annual CTC"
    assert saved["id"]


@pytest.mark.asyncio
async def test_restating_a_similar_fact_replaces_it_instead_of_duplicating(fake_collection):
    """Reproduces a real pile-up: the recruiter restated the same salary
    formula 3 times (once with a wrong multiplier) and all 3 got saved
    separately, feeding the LLM contradictory rules at once. A restatement
    must replace the old fact, not coexist with it."""
    first = await knowledge_service.add_fact(
        "Convert monthly salary (LPM) to annual CTC by multiplying maximum LPM by 15 and subtracting 5 LPA from the resulting maximum value.",
        collection=fake_collection,
    )
    second = await knowledge_service.add_fact(
        "Convert monthly salary (LPM) to annual CTC: LPM * 12 - 5 (in Lakhs).",
        collection=fake_collection,
    )
    facts = await knowledge_service.list_facts(collection=fake_collection)
    assert len(facts) == 1, "restating the same rule must replace it, not add a second copy"
    assert facts[0]["text"] == second["text"]
    assert first["id"] != second["id"]


@pytest.mark.asyncio
async def test_unrelated_facts_both_coexist(fake_collection):
    await knowledge_service.add_fact("Convert monthly salary to annual by x12.", collection=fake_collection)
    await knowledge_service.add_fact("Always exclude referral-only consultancies.", collection=fake_collection)
    facts = await knowledge_service.list_facts(collection=fake_collection)
    assert len(facts) == 2


@pytest.mark.asyncio
async def test_add_fact_rejects_blank_text(fake_collection):
    saved = await knowledge_service.add_fact("   ", collection=fake_collection)
    assert saved is None
    assert await knowledge_service.list_facts(collection=fake_collection) == []


@pytest.mark.asyncio
async def test_list_facts_newest_first(fake_collection):
    fake_collection.docs["a"] = {"_id": "a", "text": "older", "session_id": None, "created_at": datetime(2026, 1, 1)}
    fake_collection.docs["b"] = {"_id": "b", "text": "newer", "session_id": None, "created_at": datetime(2026, 2, 1)}
    facts = await knowledge_service.list_facts(collection=fake_collection)
    assert [f["text"] for f in facts] == ["newer", "older"]


@pytest.mark.asyncio
async def test_delete_fact_removes_it(fake_collection):
    saved = await knowledge_service.add_fact("Always exclude referral-only consultancies", collection=fake_collection)
    ok = await knowledge_service.delete_fact(saved["id"], collection=fake_collection)
    assert ok is True
    assert await knowledge_service.list_facts(collection=fake_collection) == []


@pytest.mark.asyncio
async def test_delete_fact_returns_false_for_unknown_id(fake_collection):
    ok = await knowledge_service.delete_fact(str(ObjectId()), collection=fake_collection)
    assert ok is False


@pytest.mark.asyncio
async def test_mongo_failure_is_swallowed_not_raised():
    class ExplodingCollection:
        async def insert_one(self, *_a, **_k):
            raise RuntimeError("mongo down")

        def find(self):
            raise RuntimeError("mongo down")

        async def delete_one(self, *_a, **_k):
            raise RuntimeError("mongo down")

    coll = ExplodingCollection()
    assert await knowledge_service.add_fact("x", collection=coll) is None
    assert await knowledge_service.list_facts(collection=coll) == []
    assert await knowledge_service.delete_fact(str(ObjectId()), collection=coll) is False
