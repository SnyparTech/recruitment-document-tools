"""
Cross-session recruiter knowledge base — durable facts/rules stated mid-chat
(a salary-conversion formula, a standing exclusion rule, a policy) that
should apply to every FUTURE chat, not just the session they were said in.
Same spirit as preference_service.py's active_in learning, but for
free-text facts the LLM flags during a normal chat-edit call rather than a
narrow enum pattern — see RequirementAgent._call_llm_chat_edit's `remember`
field in its JSON contract.

Explicit-visible, not silent: every fact that gets saved is also echoed
back in that turn's chat reply ("📌 Remembered: ...") and listed/deletable
via GET/DELETE /search/knowledge — the recruiter can always see and remove
what's been retained, even though saving itself doesn't require a separate
confirm step (unlike preference_service.py's threshold+confirm flow) —
appropriate here since a stated formula/rule is low-risk and the recruiter
dictated it verbatim themselves.

Best-effort: a Mongo hiccup here must never break the chat it rode in on.
"""
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from app.core.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "recruiter_knowledge"
MAX_FACTS = 50  # keeps the system-prompt injection bounded — oldest facts drop off first

# A restated fact (recruiter re-explaining the same rule, possibly
# correcting a number) scores well above this on word-overlap against the
# existing fact it's restating — confirmed against a real pile-up this
# caused: 3 near-identical salary-formula facts (one with a wrong
# multiplier) all got saved separately because nothing ever checked for
# overlap, so the recruiter kept having to restate it and the system prompt
# ended up feeding the LLM contradictory rules at once. 0.0 for genuinely
# unrelated facts, 0.38-0.7 for real restatements/corrections — calibrated
# against that actual data.
_DUPLICATE_SIMILARITY_THRESHOLD = 0.3

_SHORT_TIMEOUT_MS = 400
_client: Optional[AsyncIOMotorClient] = None


def get_collection() -> AsyncIOMotorCollection:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.MONGODB_URI, serverSelectionTimeoutMS=_SHORT_TIMEOUT_MS)
    return _client[settings.MONGODB_DB_NAME][COLLECTION_NAME]


def _tokens(text: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) >= 3}


def _similarity(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


async def add_fact(text: str, session_id: Optional[str] = None, collection=None) -> Optional[Dict[str, Any]]:
    """Saves a fact, replacing (not duplicating) any existing fact that's
    clearly a restatement of the same rule — see _DUPLICATE_SIMILARITY_THRESHOLD.
    A restatement is treated as a correction: the recruiter saying it again
    usually means the old version was wrong or imprecise, so the new text
    wins rather than coexisting as a second, possibly-contradictory rule."""
    text = (text or "").strip()
    if not text:
        return None
    try:
        coll = collection or get_collection()
        existing = await list_facts(collection=coll)
        for fact in existing:
            if _similarity(text, fact["text"]) >= _DUPLICATE_SIMILARITY_THRESHOLD:
                await delete_fact(fact["id"], collection=coll)
        doc = {"text": text, "session_id": session_id, "created_at": datetime.utcnow()}
        result = await coll.insert_one(doc)
        doc["_id"] = result.inserted_id
        return _serialize(doc)
    except Exception as exc:
        logger.warning("Could not save knowledge-base fact (%s) — continuing without it.", exc)
        return None


async def list_facts(collection=None) -> List[Dict[str, Any]]:
    try:
        coll = collection or get_collection()
        cursor = coll.find().sort("created_at", -1).limit(MAX_FACTS)
        return [_serialize(doc) async for doc in cursor]
    except Exception as exc:
        logger.warning("Could not list knowledge-base facts (%s) — continuing with none.", exc)
        return []


async def delete_fact(fact_id: str, collection=None) -> bool:
    try:
        from bson import ObjectId
        coll = collection or get_collection()
        result = await coll.delete_one({"_id": ObjectId(fact_id)})
        return result.deleted_count > 0
    except Exception as exc:
        logger.warning("Could not delete knowledge-base fact %s (%s).", fact_id, exc)
        return False


def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "text": doc["text"],
        "created_at": doc["created_at"].isoformat() if doc.get("created_at") else None,
    }
