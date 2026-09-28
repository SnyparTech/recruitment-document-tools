"""
MetaWhatsAppService — the ONLY code in this codebase allowed to talk to the
WhatsApp Business Platform, and only via its official Graph API endpoints.

IMPORTANT — WhatsApp Groups capability:
As of the currently documented Meta WhatsApp Business Platform (Cloud API),
there is NO endpoint to create, join, or post into a consumer WhatsApp Group
from a business account. The Cloud API's messaging model is business-to-
individual-customer only (session messages within a 24h customer-service
window, or business-initiated template messages any time). This is a
platform capability limit, not a missing-implementation gap — see
`check_operation_supported()` below, which is the single source of truth
other services consult before attempting any send. `send_to_group()` exists
only to make that limitation explicit and machine-checkable; it never
attempts a workaround and never calls any endpoint.

The practical substitute this pipeline implements instead is a configured
broadcast list: the JD message is sent individually, via the official
`/{phone_number_id}/messages` endpoint, to each opted-in recipient number in
WHATSAPP_BROADCAST_RECIPIENTS. That IS an officially supported operation.

Never logs: access tokens, Authorization headers, or full request payloads.
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.schemas.messages import MetaApiResult

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 2
_RETRY_BASE_DELAY_SECONDS = 0.5


class MetaWhatsAppService:
    """
    Capability map is deliberately explicit and centralized: every other
    service (PolicyService, RecruitmentPipeline) must ask this before
    assuming an operation will work, rather than each guessing independently.
    """

    CAPABILITIES: Dict[str, bool] = {
        "send_text_message": True,       # session message; requires an open 24h customer-service window
        "send_template_message": True,   # business-initiated; requires a pre-approved template
        "send_broadcast": True,          # our own composition of send_text/template per recipient — officially supported per-message
        "create_group": False,           # not exposed by the Cloud API at all
        "send_to_group": False,          # not exposed by the Cloud API at all
    }

    UNSUPPORTED_REASON = (
        "The official Meta WhatsApp Business Platform (Cloud API) has no endpoint "
        "to create or post into a WhatsApp Group from a business account. Messaging "
        "is business-to-individual only (session or template messages)."
    )

    def __init__(
        self,
        access_token: Optional[str] = None,
        phone_number_id: Optional[str] = None,
        api_version: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: float = 20.0,
    ):
        self.access_token = access_token or settings.META_ACCESS_TOKEN
        self.phone_number_id = phone_number_id or settings.META_PHONE_NUMBER_ID
        self.api_version = api_version or settings.META_API_VERSION
        self.base_url = (base_url or settings.META_API_BASE_URL).rstrip("/")
        self.timeout_seconds = timeout_seconds

    def check_operation_supported(self, operation: str) -> tuple[bool, Optional[str]]:
        supported = self.CAPABILITIES.get(operation, False)
        if not supported:
            return False, self.UNSUPPORTED_REASON
        if not self.access_token or not self.phone_number_id:
            return False, "Meta WhatsApp API credentials (META_ACCESS_TOKEN / META_PHONE_NUMBER_ID) are not configured."
        return True, None

    def _messages_url(self) -> str:
        return f"{self.base_url}/{self.api_version}/{self.phone_number_id}/messages"

    async def send_to_group(self, *_args: Any, **_kwargs: Any) -> MetaApiResult:
        """Always returns 'unsupported' without making any request — see module docstring."""
        logger.info("send_to_group() called — official API has no group-messaging endpoint; refusing without a request.")
        return MetaApiResult(ok=False, status="unsupported", reason=self.UNSUPPORTED_REASON)

    async def send_text_message(self, to: str, body: str) -> MetaApiResult:
        supported, reason = self.check_operation_supported("send_text_message")
        if not supported:
            return MetaApiResult(ok=False, status="unsupported", reason=reason, destination=to)
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": body},
        }
        return await self._post_with_retry(payload, destination=to)

    async def send_template_message(
        self, to: str, template_name: str, language: Optional[str] = None, components: Optional[List[dict]] = None
    ) -> MetaApiResult:
        supported, reason = self.check_operation_supported("send_template_message")
        if not supported:
            return MetaApiResult(ok=False, status="unsupported", reason=reason, destination=to)
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language or settings.WHATSAPP_TEMPLATE_LANGUAGE},
                **({"components": components} if components else {}),
            },
        }
        return await self._post_with_retry(payload, destination=to)

    async def send_broadcast(self, recipients: List[str], body: str) -> List[MetaApiResult]:
        """
        The officially-supported substitute for "post to a WhatsApp Group":
        send the same message individually to each configured recipient.
        Uses the template (if configured) so it works outside a customer's
        24h session window; falls back to a plain text session message
        otherwise (only reaches recipients who've messaged the business
        number in the last 24h — flagged in the result's `reason` when used).
        """
        results: List[MetaApiResult] = []
        for to in recipients:
            to = to.strip()
            if not to:
                continue
            if settings.WHATSAPP_TEMPLATE_NAME:
                result = await self.send_template_message(to, settings.WHATSAPP_TEMPLATE_NAME)
            else:
                result = await self.send_text_message(to, body)
                if result.ok:
                    result.reason = (
                        "Sent as a session text message — only delivered if this recipient messaged "
                        "the business number within the last 24h. Configure WHATSAPP_TEMPLATE_NAME "
                        "for reliable business-initiated delivery."
                    )
            results.append(result)
        return results

    async def _post_with_retry(self, payload: Dict[str, Any], destination: Optional[str] = None) -> MetaApiResult:
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        last_error: Optional[str] = None
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            for attempt in range(_MAX_RETRIES + 1):
                try:
                    response = await client.post(self._messages_url(), headers=headers, json=payload)
                except httpx.TimeoutException:
                    last_error = "Request to Meta API timed out."
                    logger.warning("Meta API timeout (attempt %d/%d) for destination=%s", attempt + 1, _MAX_RETRIES + 1, destination)
                    await self._maybe_backoff(attempt)
                    continue
                except httpx.HTTPError as exc:
                    last_error = f"Transport error calling Meta API: {exc.__class__.__name__}"
                    logger.warning("Meta API transport error (attempt %d/%d): %s", attempt + 1, _MAX_RETRIES + 1, exc.__class__.__name__)
                    await self._maybe_backoff(attempt)
                    continue

                if response.status_code == 200:
                    data = response.json()
                    wamid = None
                    try:
                        wamid = data["messages"][0]["id"]
                    except (KeyError, IndexError, TypeError):
                        pass
                    logger.info("Meta API send succeeded (status=200, destination=%s)", destination)
                    return MetaApiResult(ok=True, status="sent", message_id=wamid, destination=destination)

                # Never log headers/payload (contains the access token / recipient
                # PII respectively) — only the structured error Meta returns.
                error_body = _safe_error_body(response)
                logger.warning(
                    "Meta API error (status=%d, destination=%s): %s",
                    response.status_code, destination, error_body.get("message"),
                )

                if response.status_code in _RETRYABLE_STATUS_CODES and attempt < _MAX_RETRIES:
                    await self._maybe_backoff(attempt)
                    continue

                return MetaApiResult(
                    ok=False,
                    status="failed",
                    destination=destination,
                    reason=error_body.get("message") or f"Meta API returned HTTP {response.status_code}",
                    raw_error_code=str(error_body.get("code")) if error_body.get("code") is not None else None,
                )

        return MetaApiResult(ok=False, status="failed", destination=destination, reason=last_error or "Meta API request failed after retries.")

    @staticmethod
    async def _maybe_backoff(attempt: int) -> None:
        await asyncio.sleep(_RETRY_BASE_DELAY_SECONDS * (2 ** attempt))


def _safe_error_body(response: httpx.Response) -> Dict[str, Any]:
    try:
        data = response.json()
        err = data.get("error", {})
        return {"message": err.get("message", "Unknown error"), "code": err.get("code")}
    except Exception:
        return {"message": f"HTTP {response.status_code}", "code": None}
