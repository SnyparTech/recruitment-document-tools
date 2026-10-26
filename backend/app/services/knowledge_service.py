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
from datetime import datetime
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from app.core.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "recruiter_knowledge"
MAX_FACTS = 50  # keeps the system-prompt injection bounded — oldest facts drop off first

_SHORT_TIMEOUT_MS = 400
_client: Optional[AsyncIOMotorClient] = None


def get_collection() -> AsyncIOMotorCollection:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.MONGODB_URI, serverSelectionTimeoutMS=_SHORT_TIMEOUT_MS)
    return _client[settings.MONGODB_DB_NAME][COLLECTION_NAME]


async def add_fact(text: str, session_id: Optional[str] = None, collection=None) -> Optional[Dict[str, Any]]:
    text = (text or "").strip()
    if not text:
        return None
    try:
        coll = collection or get_collection()
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
