"""Schemas for WhatsApp message delivery tracking (the `messages` collection)."""
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class MessageStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    BLOCKED = "blocked"
    DUPLICATE = "duplicate"
    REJECTED = "rejected"
    UNSUPPORTED = "unsupported"


class MessageRecord(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    message_id: Optional[str] = None  # Meta's wamid, once sent
    job_id: str
    destination: Optional[str] = None
    status: MessageStatus = MessageStatus.PENDING
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None

    model_config = {"populate_by_name": True}


class MetaApiResult(BaseModel):
    """Normalized result of any MetaWhatsAppService call — success, structured
    failure, or explicit unsupported-operation, never a raw/opaque exception."""
    ok: bool
    status: str  # "sent" | "failed" | "unsupported"
    message_id: Optional[str] = None
    destination: Optional[str] = None
    reason: Optional[str] = None
    raw_error_code: Optional[str] = None


class WebhookStatusEvent(BaseModel):
    """A single status entry from Meta's `messages` webhook payload."""
    message_id: str
    status: str
    timestamp: Optional[str] = None
    recipient_id: Optional[str] = None
    error_code: Optional[str] = None
    error_title: Optional[str] = None
