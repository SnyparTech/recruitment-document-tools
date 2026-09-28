"""
MessageTrackingService — records WhatsApp send attempts/results and applies
Meta's delivery-status webhook events to them. Thin wrapper over JDRepository
so the pipeline and the webhook route share one place that knows how a
MetaApiResult / webhook event maps onto a stored MessageRecord.
"""
import logging
from typing import Any, Dict, Optional

from app.schemas.messages import MessageRecord, MessageStatus, MetaApiResult, WebhookStatusEvent
from app.services.jd_repository import JDRepository

logger = logging.getLogger(__name__)

# Meta's webhook status strings map directly onto ours except where noted.
_WEBHOOK_STATUS_MAP = {
    "sent": MessageStatus.SENT,
    "delivered": MessageStatus.DELIVERED,
    "read": MessageStatus.READ,
    "failed": MessageStatus.FAILED,
}


class MessageTrackingService:
    def __init__(self, repository: Optional[JDRepository] = None):
        self.repository = repository or JDRepository()

    async def record_result(self, job_id: str, destination: Optional[str], result: MetaApiResult) -> str:
        status_map = {
            "sent": MessageStatus.SENT,
            "failed": MessageStatus.FAILED,
            "unsupported": MessageStatus.UNSUPPORTED,
        }
        status = status_map.get(result.status, MessageStatus.FAILED)
        doc: Dict[str, Any] = {
            "job_id": job_id,
            "destination": destination,
            "message_id": result.message_id,
            "status": status.value,
            "error": result.reason if not result.ok else None,
        }
        if result.ok:
            from datetime import datetime
            doc["sent_at"] = datetime.utcnow()
        record_id = await self.repository.create_message(doc)
        logger.info("Recorded message result job_id=%s status=%s ok=%s", job_id, status.value, result.ok)
        return record_id

    async def record_rejection(self, job_id: str, destination: Optional[str], reason: str, status: MessageStatus) -> str:
        doc = {"job_id": job_id, "destination": destination, "status": status.value, "error": reason}
        return await self.repository.create_message(doc)

    async def apply_webhook_event(self, event: WebhookStatusEvent) -> bool:
        """Applies one delivery-status event from Meta's webhook. Returns True
        if a matching tracked message was found and updated."""
        mapped = _WEBHOOK_STATUS_MAP.get(event.status.lower())
        if mapped is None:
            logger.info("Ignoring unrecognized webhook status '%s' for message %s", event.status, event.message_id)
            return False

        updates: Dict[str, Any] = {"status": mapped.value}
        if event.error_code:
            updates["error"] = f"{event.error_code}: {event.error_title or ''}".strip(": ")

        from datetime import datetime
        now = datetime.utcnow()
        if mapped == MessageStatus.DELIVERED:
            updates["delivered_at"] = now
        elif mapped == MessageStatus.READ:
            updates["read_at"] = now
        elif mapped == MessageStatus.FAILED:
            updates["failed_at"] = now

        updated = await self.repository.update_message_by_wamid(event.message_id, updates)
        if not updated:
            logger.warning("Webhook status update for unknown message_id=%s (no tracked message found)", event.message_id)
        return updated

    async def get_status(self, message_record_id: str) -> Optional[Dict[str, Any]]:
        return await self.repository.get_message(message_record_id)
