"""
Tests for preference_service.py — the active_in widening pattern detector
(Phase 2 of the chat-session work). Uses a small fake Motor-collection
double (no real MongoDB needed) since this repo has no Mongo test fixtures
yet and the service is explicitly best-effort/injectable for this reason.
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import pytest
from app.services import preference_service


class _FakeUpdateResult:
    def __init__(self, matched_count):
        self.matched_count = matched_count


class FakeCollection:
    """Minimal in-memory double for the handful of Motor operations
    preference_service actually uses: update_one (with upsert/$inc/$set/
    $setOnInsert), find_one (with a status/count filter and a $regex filter)."""

    def __init__(self):
        self.docs = {}  # pattern_key -> doc

    async def update_one(self, filter_, update, upsert=False):
        pattern_key = filter_.get("pattern_key")
        existing = self.docs.get(pattern_key)
        status_ne = filter_.get("status", {}).get("$ne") if isinstance(filter_.get("status"), dict) else None
        matches = existing is not None and (status_ne is None or existing.get("status") != status_ne)

        if matches:
            doc = existing
        elif upsert:
            doc = dict(update.get("$setOnInsert", {}))
            self.docs[pattern_key] = doc
        else:
            return _FakeUpdateResult(matched_count=0)

        for field, amount in update.get("$inc", {}).items():
            doc[field] = doc.get(field, 0) + amount
        doc.update(update.get("$set", {}))
        return _FakeUpdateResult(matched_count=1)

    async def find_one(self, filter_, sort=None):
        candidates = list(self.docs.values())
        if "status" in filter_:
            candidates = [d for d in candidates if d.get("status") == filter_["status"]]
        if "count" in filter_:
            threshold = filter_["count"].get("$gte", 0)
            candidates = [d for d in candidates if d.get("count", 0) >= threshold]
        if "pattern_key" in filter_ and isinstance(filter_["pattern_key"], dict):
            prefix = filter_["pattern_key"]["$regex"].lstrip("^")
            candidates = [d for d in candidates if d.get("pattern_key", "").startswith(prefix)]
        if sort:
            field, direction = sort[0]
            candidates.sort(key=lambda d: d.get(field) or datetime.min, reverse=(direction == -1))
        return candidates[0] if candidates else None


@pytest.mark.asyncio
async def test_widening_is_recorded_when_final_is_wider_than_generated():
    coll = FakeCollection()
    await preference_service.record_active_in_widening("15 days", "30 days", collection=coll)
    doc = coll.docs["active_in_widened_to:30 days"]
    assert doc["count"] == 1
    assert doc["status"] == "observing"


@pytest.mark.asyncio
async def test_narrowing_is_not_recorded():
    coll = FakeCollection()
    await preference_service.record_active_in_widening("30 days", "15 days", collection=coll)
    assert coll.docs == {}


@pytest.mark.asyncio
async def test_same_value_is_not_recorded():
    coll = FakeCollection()
    await preference_service.record_active_in_widening("15 days", "15 days", collection=coll)
    assert coll.docs == {}


@pytest.mark.asyncio
async def test_missing_values_are_a_safe_no_op():
    coll = FakeCollection()
    await preference_service.record_active_in_widening(None, "30 days", collection=coll)
    await preference_service.record_active_in_widening("15 days", None, collection=coll)
    assert coll.docs == {}


@pytest.mark.asyncio
async def test_repeated_widening_to_same_value_accumulates_count():
    coll = FakeCollection()
    for _ in range(3):
        await preference_service.record_active_in_widening("15 days", "30 days", collection=coll)
    assert coll.docs["active_in_widened_to:30 days"]["count"] == 3


@pytest.mark.asyncio
async def test_no_pending_suggestion_below_threshold():
    coll = FakeCollection()
    for _ in range(preference_service.OBSERVATION_THRESHOLD - 1):
        await preference_service.record_active_in_widening("15 days", "30 days", collection=coll)
    assert await preference_service.get_pending_suggestion(collection=coll) is None


@pytest.mark.asyncio
async def test_pending_suggestion_appears_at_threshold():
    coll = FakeCollection()
    for _ in range(preference_service.OBSERVATION_THRESHOLD):
        await preference_service.record_active_in_widening("15 days", "30 days", collection=coll)
    suggestion = await preference_service.get_pending_suggestion(collection=coll)
    assert suggestion is not None
    assert suggestion["observed_value"] == "30 days"
    assert suggestion["count"] == preference_service.OBSERVATION_THRESHOLD


@pytest.mark.asyncio
async def test_confirm_then_get_confirmed_preferences():
    coll = FakeCollection()
    for _ in range(preference_service.OBSERVATION_THRESHOLD):
        await preference_service.record_active_in_widening("15 days", "30 days", collection=coll)

    ok = await preference_service.confirm_preference("active_in_widened_to:30 days", collection=coll)
    assert ok is True

    prefs = await preference_service.get_confirmed_preferences(collection=coll)
    assert prefs == {"active_in_default": "30 days"}


@pytest.mark.asyncio
async def test_reject_stops_further_suggestions_for_that_pattern():
    coll = FakeCollection()
    for _ in range(preference_service.OBSERVATION_THRESHOLD):
        await preference_service.record_active_in_widening("15 days", "30 days", collection=coll)

    await preference_service.reject_preference("active_in_widened_to:30 days", collection=coll)
    assert await preference_service.get_pending_suggestion(collection=coll) is None

    # Even if it keeps happening after rejection, it must not re-surface or
    # silently get counted back into the rejected pattern.
    await preference_service.record_active_in_widening("15 days", "30 days", collection=coll)
    assert await preference_service.get_pending_suggestion(collection=coll) is None


@pytest.mark.asyncio
async def test_confirm_unknown_pattern_returns_false():
    coll = FakeCollection()
    ok = await preference_service.confirm_preference("does-not-exist", collection=coll)
    assert ok is False


@pytest.mark.asyncio
async def test_get_confirmed_preferences_empty_when_none_confirmed():
    coll = FakeCollection()
    for _ in range(preference_service.OBSERVATION_THRESHOLD):
        await preference_service.record_active_in_widening("15 days", "30 days", collection=coll)
    assert await preference_service.get_confirmed_preferences(collection=coll) == {}
