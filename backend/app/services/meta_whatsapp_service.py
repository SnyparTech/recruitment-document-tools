"""
MetaWhatsAppService — the ONLY code in this codebase allowed to talk to the
WhatsApp Business Platform, and only via its official Graph API endpoints.

WhatsApp Groups capability:
Meta's Business Messaging docs (developers.facebook.com/documentation/
business-messaging/whatsapp/groups) now document a Groups API: a business can
create its own group (POST /{phone_number_id}/groups), list/inspect groups it
owns, fetch an invite link, and send messages into a group it created
(POST /{phone_number_id}/messages with recipient_type="group"). Two real
constraints to know before relying on this:
  1. Requires "Official Business Account (OBA)" status on the WhatsApp
     Business Account — not every account qualifies, and there's no API to
     self-check this; a 403 from Meta on create_group is the likely signal
     if the account isn't OBA-approved.
  2. The business can only create and manage groups it made through this API.
     There's no way to "adopt" an existing consumer-created WhatsApp group or
     add arbitrary phone numbers directly — people join a created group via
     its invite link (or an approval workflow if join_approval_mode is set).
`check_operation_supported()` is the single source of truth other services
consult before attempting any send/create, so a misconfigured or
non-OBA account fails with a clear reason instead of a raw Graph API error.

The broadcast-list substitute (send the JD individually to each number in
WHATSAPP_BROADCAST_RECIPIENTS) is still implemented and still works
regardless of OBA status — useful as a fallback if group creation 403s.

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
        "create_group": True,            # requires Official Business Account (OBA) status — see module docstring
        "send_to_group": True,           # requires a group_id this business account created via create_group
    }

    UNSUPPORTED_REASON = (
        "Meta WhatsApp group operations require Official Business Account (OBA) "
        "status and credentials to be configured. If this keeps failing, the "
        "account likely isn't OBA-approved yet — see module docstring."
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

    def _groups_url(self) -> str:
        return f"{self.base_url}/{self.api_version}/{self.phone_number_id}/groups"

    def _node_url(self, node_id: str, suffix: str = "") -> str:
        return f"{self.base_url}/{self.api_version}/{node_id}{suffix}"

    async def send_to_group(self, group_id: str, body: str) -> MetaApiResult:
        """Sends a text message into a group this business account created
        (via create_group). group_id is the id returned by create_group/
        list_groups, not a consumer WhatsApp group invite code."""
        supported, reason = self.check_operation_supported("send_to_group")
        if not supported:
            return MetaApiResult(ok=False, status="unsupported", reason=reason, destination=group_id)
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "group",
            "to": group_id,
            "type": "text",
            "text": {"preview_url": False, "body": body},
        }
        return await self._post_with_retry(payload, destination=group_id)

    async def create_group(
        self, subject: str, description: Optional[str] = None, join_approval_mode: Optional[str] = None
    ) -> Dict[str, Any]:
        """Creates a new group owned by this business account. Returns a
        normalized {ok, data|reason} dict (group metadata isn't a 'message
        send', so MetaApiResult doesn't fit — no point stretching it)."""
        supported, reason = self.check_operation_supported("create_group")
        if not supported:
            return {"ok": False, "reason": reason}
        payload: Dict[str, Any] = {"messaging_product": "whatsapp", "subject": subject}
        if description:
            payload["description"] = description
        if join_approval_mode:
            payload["join_approval_mode"] = join_approval_mode
        return await self._graph_request("POST", self._groups_url(), json=payload)

    async def list_groups(self, limit: int = 25, after: Optional[str] = None, before: Optional[str] = None) -> Dict[str, Any]:
        supported, reason = self.check_operation_supported("create_group")
        if not supported:
            return {"ok": False, "reason": reason}
        params: Dict[str, Any] = {"limit": limit}
        if after:
            params["after"] = after
        if before:
            params["before"] = before
        return await self._graph_request("GET", self._groups_url(), params=params)

    async def get_group(self, group_id: str, fields: Optional[str] = None) -> Dict[str, Any]:
        supported, reason = self.check_operation_supported("create_group")
        if not supported:
            return {"ok": False, "reason": reason}
        params = {"fields": fields} if fields else None
        return await self._graph_request("GET", self._node_url(group_id), params=params)

    async def get_invite_link(self, group_id: str) -> Dict[str, Any]:
        supported, reason = self.check_operation_supported("create_group")
        if not supported:
            return {"ok": False, "reason": reason}
        return await self._graph_request("GET", self._node_url(group_id, "/invite_link"))

    async def reset_invite_link(self, group_id: str) -> Dict[str, Any]:
        supported, reason = self.check_operation_supported("create_group")
        if not supported:
            return {"ok": False, "reason": reason}
        return await self._graph_request("POST", self._node_url(group_id, "/invite_link"), json={"messaging_product": "whatsapp"})

    async def _graph_request(
        self, method: str, url: str, json: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.request(method, url, headers=headers, json=json, params=params)
        except httpx.HTTPError as exc:
            logger.warning("Meta Graph API transport error (%s %s): %s", method, url, exc.__class__.__name__)
            return {"ok": False, "reason": f"Transport error calling Meta API: {exc.__class__.__name__}"}

        if response.status_code == 200:
            return {"ok": True, "data": response.json()}

        error_body = _safe_error_body(response)
        logger.warning("Meta Graph API error (%s %s, status=%d): %s", method, url, response.status_code, error_body.get("message"))
        return {
            "ok": False,
            "reason": error_body.get("message") or f"Meta API returned HTTP {response.status_code}",
            "raw_error_code": error_body.get("code"),
        }

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
