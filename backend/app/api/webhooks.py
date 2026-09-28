"""
Meta WhatsApp webhook: subscription verification (GET) + delivery-status
events (POST). This is the only inbound entry point Meta calls into this
service — never logs the raw request body (may contain recipient PII), only
counts/statuses.
"""
import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse

from app.core.config import settings
from app.schemas.messages import WebhookStatusEvent
from app.services.jd_repository import JDRepository
from app.services.message_tracking_service import MessageTrackingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])

_tracking_service = MessageTrackingService(repository=JDRepository())


@router.get("/whatsapp", summary="Meta webhook subscription verification handshake")
async def verify_webhook(
    hub_mode: str = Query(default="", alias="hub.mode"),
    hub_verify_token: str = Query(default="", alias="hub.verify_token"),
    hub_challenge: str = Query(default="", alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token and hub_verify_token == settings.META_WEBHOOK_VERIFY_TOKEN:
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={
        "error": "WEBHOOK_VERIFICATION_FAILED", "message": "hub.verify_token did not match configured META_WEBHOOK_VERIFY_TOKEN.",
    })


@router.post("/whatsapp", summary="Receive WhatsApp delivery-status events from Meta")
async def receive_webhook(request: Request):
    try:
        payload: Dict[str, Any] = await request.json()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
            "error": "INVALID_PAYLOAD", "message": "Webhook body was not valid JSON.",
        })

    applied = 0
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value", {}) or {}
            for status_entry in value.get("statuses", []) or []:
                errors = status_entry.get("errors") or []
                first_error = errors[0] if errors else {}
                event = WebhookStatusEvent(
                    message_id=status_entry.get("id", ""),
                    status=status_entry.get("status", ""),
                    timestamp=status_entry.get("timestamp"),
                    recipient_id=status_entry.get("recipient_id"),
                    error_code=str(first_error.get("code")) if first_error.get("code") is not None else None,
                    error_title=first_error.get("title"),
                )
                if event.message_id and await _tracking_service.apply_webhook_event(event):
                    applied += 1

    logger.info("Webhook received: %d status event(s) applied", applied)
    return {"received": True, "applied": applied}
