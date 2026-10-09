"""
Recruiter preference learning — Phase 2 of the chat-session work (see
docs/LLM_MODEL_COMPARISON.md's neighbor discussion; Phase 1 was multi-session
chat in chat_session_service.py).

Scope, deliberately narrow: tracks ONE pattern to start — how far the
recruiter ends up widening `active_in` beyond what the LLM originally
proposed (almost always DEFAULT_ACTIVE_IN="15 days", see requirement_agent.py)
by the time they actually apply a plan to Resdex. Keyword-level patterns
(e.g. "always demotes cloud-platform keywords") are free-text and JD-specific
— fuzzier to generalize safely — intentionally left for a later phase once
this simpler, cleanly-comparable enum pattern is proven out.

Design: NEVER let a Mongo hiccup break the actual search/chat flow — every
public function here is best-effort and swallows its own exceptions,
returning a safe empty/None result instead of propagating. Mongo is a
"nice to have personalization" layer on top of a pipeline that must keep
working with zero configured preferences.

Deliberately does NOT reuse app.db.mongodb's shared client: that one uses a
5s serverSelectionTimeoutMS, fine for the JD/WhatsApp pipeline (not latency-
sensitive) but would add up to 5s of dead weight to EVERY /search/candidates
and /plan/chat call — on the hot path of every chat message — whenever Mongo
isn't configured/running, which is the default state until someone sets it
up. This module's own client uses a short timeout instead, so an absent
Mongo fails fast and stays invisible to the recruiter.

Explicit-confirmation model (not silent/implicit learning, per the user's
own stated requirement): a pattern only gets applied to future plans after
it's been observed OBSERVATION_THRESHOLD times AND the recruiter has
explicitly confirmed it via POST /search/preferences/{pattern_key}/confirm.
"""
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from app.core.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "recruiter_preferences"
OBSERVATION_THRESHOLD = 3

_SHORT_TIMEOUT_MS = 400
_client: Optional[AsyncIOMotorClient] = None


def get_collection(name: str = COLLECTION_NAME) -> AsyncIOMotorCollection:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.MONGODB_URI, serverSelectionTimeoutMS=_SHORT_TIMEOUT_MS)
    return _client[settings.MONGODB_DB_NAME][name]

# Resdex's own active_in options, day-equivalents — same mapping as
# RequirementAgent._ACTIVE_IN_DAYS, duplicated rather than imported to avoid
# a service -> agent dependency for one small dict.
_ACTIVE_IN_DAYS = {
    "3 days": 3, "7 days": 7, "15 days": 15, "30 days": 30,
    "2 months": 60, "3 months": 90, "6 months": 180,
}


def _pattern_key(active_in_value: str) -> str:
    return f"active_in_widened_to:{active_in_value}"


async def record_active_in_widening(
    generated_value: Optional[str], final_value: Optional[str], collection=None
) -> None:
    """Call when a plan is actually applied (POST /search/plan). If the
    recruiter ended up with a WIDER active_in than what was originally
    generated, records one occurrence of that specific target value.
    Best-effort — logs and returns on any failure, never raises."""
    if not generated_value or not final_value or generated_value == final_value:
        return
    gen_days = _ACTIVE_IN_DAYS.get(generated_value)
    final_days = _ACTIVE_IN_DAYS.get(final_value)
    if gen_days is None or final_days is None or final_days <= gen_days:
        return  # not a widening (or an unrecognized value) — nothing to learn

    try:
        coll = collection or get_collection(COLLECTION_NAME)
        now = datetime.utcnow()
        await coll.update_one(
            {"pattern_key": _pattern_key(final_value), "status": {"$ne": "rejected"}},
            {
                "$inc": {"count": 1},
                "$set": {"last_seen": now, "observed_value": final_value},
                "$setOnInsert": {"pattern_key": _pattern_key(final_value), "first_seen": now, "status": "observing"},
            },
            upsert=True,
        )
    except Exception as exc:
        logger.warning("Could not record active_in preference observation (%s) — continuing without it.", exc)


async def get_pending_suggestion(collection=None) -> Optional[Dict[str, Any]]:
    """Returns the first pattern that's crossed OBSERVATION_THRESHOLD and
    hasn't been confirmed/rejected yet, or None. Best-effort — a Mongo
    failure here must never block the chat/search UI, just means no
    suggestion is shown this time."""
    try:
        coll = collection or get_collection(COLLECTION_NAME)
        doc = await coll.find_one({"status": "observing", "count": {"$gte": OBSERVATION_THRESHOLD}})
        if not doc:
            return None
        return {
            "pattern_key": doc["pattern_key"],
            "observed_value": doc["observed_value"],
            "count": doc["count"],
        }
    except Exception as exc:
        logger.warning("Could not fetch pending preference suggestion (%s) — continuing without it.", exc)
        return None


async def confirm_preference(pattern_key: str, collection=None) -> bool:
    try:
        coll = collection or get_collection(COLLECTION_NAME)
        result = await coll.update_one(
            {"pattern_key": pattern_key},
            {"$set": {"status": "confirmed", "confirmed_at": datetime.utcnow()}},
        )
        return result.matched_count > 0
    except Exception as exc:
        logger.warning("Could not confirm preference %s (%s).", pattern_key, exc)
        return False


async def reject_preference(pattern_key: str, collection=None) -> bool:
    try:
        coll = collection or get_collection(COLLECTION_NAME)
        result = await coll.update_one(
            {"pattern_key": pattern_key},
            {"$set": {"status": "rejected"}},
        )
        return result.matched_count > 0
    except Exception as exc:
        logger.warning("Could not reject preference %s (%s).", pattern_key, exc)
        return False


async def get_confirmed_preferences(collection=None) -> Dict[str, str]:
    """Returns {"active_in_default": "<value>"} if a confirmed active_in
    widening preference exists, else {}. Best-effort — Mongo being down just
    means plans generate with the normal hardcoded default, same as today."""
    try:
        coll = collection or get_collection(COLLECTION_NAME)
        doc = await coll.find_one(
            {"pattern_key": {"$regex": "^active_in_widened_to:"}, "status": "confirmed"},
            sort=[("confirmed_at", -1)],
        )
        if not doc:
            return {}
        return {"active_in_default": doc["observed_value"]}
    except Exception as exc:
        logger.warning("Could not fetch confirmed preferences (%s) — using defaults.", exc)
        return {}
