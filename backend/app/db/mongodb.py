"""
MongoDB connection for the Recruitment JD -> WhatsApp pipeline.

Uses Motor's async client, which is lazy by construction (it does not open a
socket until the first operation), so importing this module never blocks or
crashes app startup even if MongoDB isn't running yet — the same "fail safe,
report clearly" philosophy as the rest of this pipeline. Actual connection
errors surface only when a repository method is called, and are caught there.

This is separate from `state_persistence.py`, which backs the unrelated
Resdex SearchPlan feature with a flat JSON file — different domain, different
durability needs (this one needs querying/dedup by hash, that one doesn't).
"""
import logging
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: Optional[AsyncIOMotorClient] = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.MONGODB_URI, serverSelectionTimeoutMS=5000)
    return _client


def get_db() -> AsyncIOMotorDatabase:
    return get_client()[settings.MONGODB_DB_NAME]


def get_collection(name: str) -> AsyncIOMotorCollection:
    return get_db()[name]


async def ping() -> bool:
    """Best-effort connectivity check — used by health/status endpoints, never
    raises; a Mongo outage should be reported, not crash the caller."""
    try:
        await get_client().admin.command("ping")
        return True
    except Exception as exc:
        logger.warning("MongoDB ping failed: %s", exc)
        return False


async def close_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
