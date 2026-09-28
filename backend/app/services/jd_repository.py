"""
JDRepository — MongoDB persistence for jobs, WhatsApp message tracking, and
Gmail dedup state. Kept as one thin repository (rather than three) because all
three collections are written from the same RecruitmentPipeline run and share
connection/error handling; each method is still narrow and single-purpose,
and callers (pipeline, API routes) depend on this, never on `db/mongodb.py`
directly, so the storage layer stays swappable.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId
from bson.errors import InvalidId

from app.db.mongodb import get_collection
from app.schemas.jd import JobStatus, WhatsAppSendStatus
from app.schemas.messages import MessageStatus

logger = logging.getLogger(__name__)

JOBS_COLLECTION = "jobs"
MESSAGES_COLLECTION = "messages"
GMAIL_PROCESSED_COLLECTION = "gmail_processed"


def _oid_str(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if doc is None:
        return None
    doc = dict(doc)
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc


class JDRepository:
    # ---------------------------------------------------------------- jobs --
    async def create_job(self, job_doc: Dict[str, Any]) -> str:
        job_doc = dict(job_doc)
        job_doc.setdefault("created_at", datetime.utcnow())
        job_doc["updated_at"] = datetime.utcnow()
        result = await get_collection(JOBS_COLLECTION).insert_one(job_doc)
        return str(result.inserted_id)

    async def update_job(self, job_id: str, updates: Dict[str, Any]) -> bool:
        try:
            oid = ObjectId(job_id)
        except (InvalidId, TypeError):
            return False
        updates = dict(updates)
        updates["updated_at"] = datetime.utcnow()
        result = await get_collection(JOBS_COLLECTION).update_one({"_id": oid}, {"$set": updates})
        return result.matched_count > 0

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        try:
            oid = ObjectId(job_id)
        except (InvalidId, TypeError):
            return None
        doc = await get_collection(JOBS_COLLECTION).find_one({"_id": oid})
        return _oid_str(doc)

    async def find_job_by_hash(self, jd_hash: str) -> Optional[Dict[str, Any]]:
        doc = await get_collection(JOBS_COLLECTION).find_one(
            {"jd_hash": jd_hash, "status": {"$ne": JobStatus.FAILED.value}},
            sort=[("created_at", -1)],
        )
        return _oid_str(doc)

    async def find_job_by_gmail_id(self, gmail_message_id: str) -> Optional[Dict[str, Any]]:
        doc = await get_collection(JOBS_COLLECTION).find_one({"gmail_message_id": gmail_message_id})
        return _oid_str(doc)

    async def list_jobs(self, limit: int = 50, skip: int = 0) -> List[Dict[str, Any]]:
        cursor = get_collection(JOBS_COLLECTION).find().sort("created_at", -1).skip(skip).limit(limit)
        return [_oid_str(doc) async for doc in cursor]

    # ------------------------------------------------------------ messages --
    async def create_message(self, message_doc: Dict[str, Any]) -> str:
        message_doc = dict(message_doc)
        message_doc.setdefault("created_at", datetime.utcnow())
        result = await get_collection(MESSAGES_COLLECTION).insert_one(message_doc)
        return str(result.inserted_id)

    async def update_message_by_id(self, message_record_id: str, updates: Dict[str, Any]) -> bool:
        try:
            oid = ObjectId(message_record_id)
        except (InvalidId, TypeError):
            return False
        result = await get_collection(MESSAGES_COLLECTION).update_one({"_id": oid}, {"$set": updates})
        return result.matched_count > 0

    async def update_message_by_wamid(self, wamid: str, updates: Dict[str, Any]) -> bool:
        """Used by the webhook handler — Meta's delivery-status events key off
        their own message id (wamid), not our Mongo _id."""
        result = await get_collection(MESSAGES_COLLECTION).update_one(
            {"message_id": wamid}, {"$set": updates}
        )
        return result.matched_count > 0

    async def get_message(self, message_record_id: str) -> Optional[Dict[str, Any]]:
        try:
            oid = ObjectId(message_record_id)
        except (InvalidId, TypeError):
            return None
        doc = await get_collection(MESSAGES_COLLECTION).find_one({"_id": oid})
        return _oid_str(doc)

    async def get_message_by_wamid(self, wamid: str) -> Optional[Dict[str, Any]]:
        doc = await get_collection(MESSAGES_COLLECTION).find_one({"message_id": wamid})
        return _oid_str(doc)

    async def count_messages_sent_since(self, since: datetime) -> int:
        return await get_collection(MESSAGES_COLLECTION).count_documents(
            {"status": {"$in": [MessageStatus.SENT.value, MessageStatus.DELIVERED.value, MessageStatus.READ.value]},
             "sent_at": {"$gte": since}}
        )

    async def find_latest_message_for_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        doc = await get_collection(MESSAGES_COLLECTION).find_one(
            {"job_id": job_id}, sort=[("created_at", -1)]
        )
        return _oid_str(doc)

    # ------------------------------------------------------------- gmail ----
    async def is_gmail_message_processed(self, gmail_message_id: str) -> bool:
        doc = await get_collection(GMAIL_PROCESSED_COLLECTION).find_one(
            {"gmail_message_id": gmail_message_id}
        )
        return doc is not None

    async def mark_gmail_message_processed(
        self, gmail_message_id: str, status: str, jd_id: Optional[str] = None
    ) -> None:
        await get_collection(GMAIL_PROCESSED_COLLECTION).update_one(
            {"gmail_message_id": gmail_message_id},
            {
                "$set": {
                    "gmail_message_id": gmail_message_id,
                    "status": status,
                    "processed_at": datetime.utcnow(),
                    "jd_id": jd_id,
                }
            },
            upsert=True,
        )
