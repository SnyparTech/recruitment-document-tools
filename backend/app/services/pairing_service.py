"""
Short-lived pairing codes: the one-time handoff from a website login to the
Chrome extension. The recruiter logs into the website (email+OTP), the
website shows an 8-character code, they paste it into the extension popup
once — the extension exchanges it for a long-lived device token (see
device_token_service.py) and never needs the code again. Avoids the
extension needing to read the website's session cookie directly, which
Manifest V3's cross-context cookie access makes unreliable (different
browser profile, incognito, cleared cookies, etc. all silently break it).
"""
import logging
import secrets
import string
import time
from typing import Optional

from pymongo import MongoClient

from app.core.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "pairing_codes"
CODE_TTL_SECONDS = 5 * 60  # 5 minutes — long enough to alt-tab to the extension, short enough to limit exposure
_TIMEOUT_MS = 3000
_ALPHABET = string.ascii_uppercase + string.digits  # no lowercase — easier to type/read aloud

_client: Optional[MongoClient] = None


def _get_collection():
    global _client
    if _client is None:
        _client = MongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=_TIMEOUT_MS)
    return _client[settings.MONGODB_DB_NAME][COLLECTION_NAME]


def create_pairing_code(email: str) -> str:
    code = "".join(secrets.choice(_ALPHABET) for _ in range(8))
    now = time.time()
    try:
        _get_collection().insert_one({
            "_id": code,
            "email": email,
            "created_at": now,
            "expires_at": now + CODE_TTL_SECONDS,
        })
    except Exception as exc:
        logger.warning("Could not create pairing code (%s).", exc)
        raise ValueError("Could not generate a pairing code. Try again shortly.")
    return code


def consume_pairing_code(code: str) -> str:
    """Single-use: deletes the code on success. Raises ValueError (safe to
    show the caller) if missing/expired/already used."""
    try:
        coll = _get_collection()
        now = time.time()
        doc = coll.find_one_and_delete({"_id": code.strip().upper(), "expires_at": {"$gt": now}})
    except Exception as exc:
        logger.warning("Could not verify pairing code (%s).", exc)
        raise ValueError("Could not verify the pairing code. Try again shortly.")
    if not doc:
        raise ValueError("Invalid or expired pairing code. Generate a new one from the website.")
    return doc["email"]
