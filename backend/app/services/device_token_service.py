"""
Long-lived device credentials for the Chrome extension — issued once via a
pairing code (see pairing_service.py) after a real website login, replacing
the extension's old standalone email+OTP device-registration flow entirely.

The token itself is only ever stored hashed (sha256) — same principle as a
password store, since this token is a durable bearer credential (unlike the
short-lived OTP codes elsewhere, which are fine in plaintext given their
10-minute window). The raw token is returned to the extension exactly once,
at pairing time, and never again.
"""
import hashlib
import logging
import secrets
import time
from typing import Optional

from pymongo import MongoClient

from app.core.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "device_tokens"
_TIMEOUT_MS = 3000

_client: Optional[MongoClient] = None


def _get_collection():
    global _client
    if _client is None:
        _client = MongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=_TIMEOUT_MS)
    return _client[settings.MONGODB_DB_NAME][COLLECTION_NAME]


def _hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


class AuthServiceUnavailable(Exception):
    """Raised when the token store itself can't be reached — callers must
    deny access (503), not treat it as "token invalid" (401/403)."""


def issue_device_token(device_id: str, email: str) -> str:
    """One device_id = one active token (re-pairing the same device_id
    overwrites its previous token, consistent with the old
    one-device-per-email model this replaces)."""
    raw_token = secrets.token_hex(32)
    now = time.time()
    try:
        _get_collection().replace_one(
            {"_id": device_id},
            {"_id": device_id, "token_hash": _hash(raw_token), "email": email, "created_at": now, "last_used_at": now},
            upsert=True,
        )
    except Exception as exc:
        logger.warning("Could not issue device token (%s).", exc)
        raise ValueError("Could not pair this device. Try again shortly.")
    return raw_token


def verify_device_token(device_id: str, raw_token: str) -> bool:
    if not device_id or not raw_token:
        return False
    try:
        coll = _get_collection()
        doc = coll.find_one({"_id": device_id})
        if not doc or not secrets.compare_digest(doc.get("token_hash", ""), _hash(raw_token)):
            return False
        coll.update_one({"_id": device_id}, {"$set": {"last_used_at": time.time()}})
        return True
    except Exception as exc:
        logger.warning("Could not verify device token (%s).", exc)
        raise AuthServiceUnavailable(str(exc))


def revoke_device(device_id: str) -> bool:
    try:
        result = _get_collection().delete_one({"_id": device_id})
        return result.deleted_count > 0
    except Exception as exc:
        logger.warning("Could not revoke device %s (%s).", device_id, exc)
        return False
