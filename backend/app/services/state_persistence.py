"""
MongoDB-backed persistence for the process-global search state (active
SearchPlan, extracted candidates, chat sessions) in backend/app/api/search.py
and services/chat_session_service.py.

Was a local JSON file (backend/.data/search_state.json). That broke on
Render specifically: the file is gitignored (never ships in the image) and
Render's container filesystem is ephemeral with no persistent-disk config in
render.yaml — every redeploy (which happens on every push) spins up a brand
new container with a brand new empty filesystem, silently wiping every
recruiter's chat sessions with no warning. Confirmed as the actual cause of
a real "my chat history disappeared" report, correlated against 3 redeploys
in 3 days. MongoDB Atlas is external to the container and survives every
redeploy/restart, which a local file fundamentally cannot.

Single document (one fixed _id) in its own collection — same "one blob"
shape the JSON file used, so callers (search.py, chat_session_service.py)
needed zero changes to their own data model, only to how load/save reach
the network (see _persist_now() in api/search.py, which now runs the
blocking save on a thread via asyncio.to_thread so a slow/unreachable Mongo
can't stall the whole event loop — same reasoning as preference_service.py's
dedicated short-timeout client).
"""
import logging
import time
from typing import Any, Dict, Optional

from pymongo import MongoClient

from app.core.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "app_state"
DOC_ID = "search_state"
_TIMEOUT_MS = 3000
_LOAD_RETRIES = 3
_LOAD_RETRY_BACKOFF_SECONDS = 2.0

_client: Optional[MongoClient] = None

# Set True only after a load_state() call actually reaches MongoDB during
# this process's startup. save_state() refuses to write while this is False
# — otherwise a single slow-to-respond Mongo connection during the narrow
# cold-start window (DNS/TLS handshake, Atlas waking up, any transient
# network blip) silently falls back to an empty dict, and the NEXT save
# (replace_one upsert) overwrites real persisted data in MongoDB with that
# empty state — turning a one-off hiccup into permanent data loss. Confirmed
# as the actual cause of a real "my chat history disappeared after a
# restart, but MongoDB itself never went down" report.
_load_ok = False


def _get_collection():
    global _client
    if _client is None:
        _client = MongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=_TIMEOUT_MS)
    return _client[settings.MONGODB_DB_NAME][COLLECTION_NAME]


def load_state() -> Dict[str, Any]:
    """Load with retries — only ever called at module-import time (before
    any event loop exists), never from inside a request handler, so
    blocking here for a few retries' worth of extra startup latency is a
    fair trade for not silently discarding real data. Sets `_load_ok` on
    success; see its docstring for why that matters."""
    global _load_ok
    last_exc = None
    for attempt in range(_LOAD_RETRIES):
        try:
            doc = _get_collection().find_one({"_id": DOC_ID})
            _load_ok = True
            if doc:
                doc.pop("_id", None)
                return doc
            return {}
        except Exception as exc:
            last_exc = exc
            if attempt < _LOAD_RETRIES - 1:
                logger.warning(
                    "Could not load persisted search state from MongoDB (attempt %d/%d: %s) — retrying in %.0fs.",
                    attempt + 1, _LOAD_RETRIES, exc, _LOAD_RETRY_BACKOFF_SECONDS,
                )
                time.sleep(_LOAD_RETRY_BACKOFF_SECONDS)
    logger.error(
        "Could not load persisted search state from MongoDB after %d attempts (%s) — running in-memory only "
        "for this process. Existing data in MongoDB is untouched; saves are disabled until a restart "
        "successfully reaches Mongo, so this failure can't overwrite it.",
        _LOAD_RETRIES, last_exc,
    )
    return {}


def save_state(
    search_plan: Optional[dict],
    plan_timestamp: float,
    candidates: list,
    candidates_timestamp: float,
    search_id: Optional[str],
    sessions: Optional[dict] = None,
    active_session_id: Optional[str] = None,
) -> None:
    """Best-effort save; a write failure (Mongo unreachable, etc.) must never
    break the request that triggered it — log and move on. Blocking/sync by
    design — callers run this via asyncio.to_thread (see api/search.py's
    _persist_now) rather than making this module async, so one slow Mongo
    write can't stall every other concurrent request on the event loop.

    `sessions` backs the requirement chat's multi-session "stage then apply"
    flow (see services/chat_session_service.py, api/search.py's
    /search/sessions routes) — each session has its own draft SearchPlan +
    chat history, separate from `search_plan` (the one the extension actually
    reads and applies to Resdex)."""
    if not _load_ok:
        logger.warning(
            "Skipping save — this process's initial state load never reached MongoDB (see the error logged at "
            "startup). Refusing to write prevents overwriting real persisted data with incomplete in-memory state."
        )
        return
    try:
        payload = {
            "_id": DOC_ID,
            "search_plan": search_plan,
            "plan_timestamp": plan_timestamp,
            "candidates": candidates,
            "candidates_timestamp": candidates_timestamp,
            "search_id": search_id,
            "sessions": sessions or {},
            "active_session_id": active_session_id,
        }
        _get_collection().replace_one({"_id": DOC_ID}, payload, upsert=True)
    except Exception as exc:
        logger.warning("Could not persist search state to MongoDB (%s) — continuing with in-memory only.", exc)
