"""
PolicyService — the mandatory safety gate before ANY WhatsApp send. Every
check is independent and fails closed: if a check can't be evaluated (e.g.
the repository call errors), that counts as "not allowed", never "allowed by
default". Returns a clear, single reason on the first failing check rather
than a vague rejection — every stage the pipeline can refuse at should say
exactly why (see PolicyCheckResult).
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.schemas.jd import JobStatus, WhatsAppSendStatus
from app.schemas.whatsapp import PolicyCheckResult
from app.services.jd_repository import JDRepository

logger = logging.getLogger(__name__)


class PolicyService:
    def __init__(self, repository: Optional[JDRepository] = None):
        self.repository = repository or JDRepository()

    async def check(
        self,
        job_doc: Dict[str, Any],
        message: str,
        meta_operation_supported: bool,
        meta_unsupported_reason: Optional[str] = None,
    ) -> PolicyCheckResult:
        checks_run: List[str] = []

        def deny(check_name: str, reason: str) -> PolicyCheckResult:
            checks_run.append(check_name)
            logger.info("Policy check '%s' denied send for job %s: %s", check_name, job_doc.get("_id"), reason)
            return PolicyCheckResult(allowed=False, reason=reason, checks_run=checks_run)

        # 1. JD must have made it through validation/storage.
        checks_run.append("jd_valid")
        status = job_doc.get("status")
        if status in (JobStatus.VALIDATION_FAILED.value, JobStatus.FAILED.value):
            return deny("jd_valid", f"JD is not in a sendable state (status={status}).")

        # 2. Message non-empty.
        checks_run.append("message_non_empty")
        if not message or not message.strip():
            return deny("message_non_empty", "Formatted WhatsApp message is empty.")

        # 3. Message length within API limits.
        checks_run.append("message_length")
        if len(message) > settings.WHATSAPP_MESSAGE_MAX_CHARS:
            return deny(
                "message_length",
                f"Message length {len(message)} exceeds the {settings.WHATSAPP_MESSAGE_MAX_CHARS}-char API limit.",
            )

        # 4. Duplicate JD.
        checks_run.append("not_duplicate")
        if status == JobStatus.DUPLICATE.value or job_doc.get("is_duplicate_of"):
            return deny("not_duplicate", "Duplicate JD detected — not sending again automatically.")

        # 5. Not already sent for this job.
        checks_run.append("not_already_sent")
        if job_doc.get("whatsapp_status") == WhatsAppSendStatus.SENT.value:
            return deny("not_already_sent", "A WhatsApp message has already been sent for this job.")

        # 6. Sending frequency / rate limit.
        checks_run.append("rate_limit")
        try:
            since = datetime.utcnow() - timedelta(hours=1)
            sent_count = await self.repository.count_messages_sent_since(since)
        except Exception as exc:
            return deny("rate_limit", f"Could not verify sending rate (fail-closed): {exc}")
        if sent_count >= settings.WHATSAPP_MAX_MESSAGES_PER_HOUR:
            return deny(
                "rate_limit",
                f"Hourly send limit reached ({sent_count}/{settings.WHATSAPP_MAX_MESSAGES_PER_HOUR}).",
            )

        # 7. Required WhatsApp configuration exists.
        checks_run.append("meta_config_present")
        if not settings.META_ACCESS_TOKEN or not settings.META_PHONE_NUMBER_ID:
            return deny(
                "meta_config_present",
                "META_ACCESS_TOKEN / META_PHONE_NUMBER_ID not configured.",
            )

        # 8. Destination configured.
        checks_run.append("destination_configured")
        if not settings.WHATSAPP_BROADCAST_RECIPIENTS.strip():
            return deny("destination_configured", "WHATSAPP_BROADCAST_RECIPIENTS is not configured.")

        # 9. Requested API operation is actually supported by the official API.
        checks_run.append("operation_supported")
        if not meta_operation_supported:
            return deny(
                "operation_supported",
                meta_unsupported_reason or "The requested WhatsApp operation is not supported by the configured official Meta API.",
            )

        # 10. No unofficial automation — structural guarantee: PolicyService only
        # ever authorizes a send through MetaWhatsAppService's official Graph API
        # client (see meta_whatsapp_service.py); there is no other send path.
        checks_run.append("official_api_only")

        # 11. Dry-run gate is enforced by the caller (RecruitmentPipeline), not
        # here, because "not sending" in dry-run isn't a POLICY rejection —
        # everything else about the message is still valid and approved.
        return PolicyCheckResult(allowed=True, reason=None, checks_run=checks_run)
