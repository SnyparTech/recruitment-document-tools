"""
Website login sessions — replaces the extension-only device-lock as the
primary gate (see services/device_token_service.py for what the extension
uses now, which is downstream of a website login via a pairing code, not a
standalone email+OTP flow of its own anymore).

A session is an opaque random token, stored in MongoDB (NOT the local
.data/ pattern — same reasoning as state_persistence.py: Render's container
disk is wiped on every redeploy, and a session store that resets on every
deploy would log out every recruiter constantly). Sliding 30-day expiry:
every successful check extends it, so active use never times out, but an
abandoned session eventually expires.

SECURITY: unlike preference_service.py / state_persistence.py (which fail
OPEN — a Mongo hiccup just means a feature silently no-ops), this module
fails CLOSED. An auth check that can't reach its backing store must deny
access, not quietly let the request through. See core/web_auth.py, which
raises 503 (not 401) specifically when Mongo itself is unreachable, so a
real outage is distinguishable from "you're not logged in."
"""
import logging
import secrets
import time
from typing import Optional

from pymongo import MongoClient

from app.core.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "website_sessions"
SESSION_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days, sliding
_TIMEOUT_MS = 3000

_client: Optional[MongoClient] = None


def _get_collection():
    global _client
    if _client is None:
        _client = MongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=_TIMEOUT_MS)
    return _client[settings.MONGODB_DB_NAME][COLLECTION_NAME]


class AuthServiceUnavailable(Exception):
    """Raised when the session store itself can't be reached — distinct
    from "no valid session", so callers can return 503 instead of 401."""


def create_session(email: str) -> str:
    token = secrets.token_hex(32)
    now = time.time()
    try:
        _get_collection().insert_one({
            "_id": token,
            "email": email,
            "created_at": now,
            "expires_at": now + SESSION_TTL_SECONDS,
        })
    except Exception as exc:
        logger.warning("Could not create website session (%s).", exc)
        raise AuthServiceUnavailable(str(exc))
    return token


def get_session_email(token: str) -> Optional[str]:
    """Returns the logged-in email for a valid, non-expired session token,
    sliding its expiry forward. Returns None for a missing/expired token.
    Raises AuthServiceUnavailable if the store itself can't be reached —
    callers must treat that as "deny", not "not logged in"."""
    if not token:
        return None
    try:
        coll = _get_collection()
        now = time.time()
        doc = coll.find_one({"_id": token, "expires_at": {"$gt": now}})
        if not doc:
            return None
        coll.update_one({"_id": token}, {"$set": {"expires_at": now + SESSION_TTL_SECONDS}})
        return doc["email"]
    except AuthServiceUnavailable:
        raise
    except Exception as exc:
        logger.warning("Could not verify website session (%s).", exc)
        raise AuthServiceUnavailable(str(exc))


def delete_session(token: str) -> None:
    try:
        _get_collection().delete_one({"_id": token})
    except Exception as exc:
        logger.warning("Could not delete website session (%s).", exc)
