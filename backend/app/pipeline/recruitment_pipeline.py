"""
RecruitmentPipeline — orchestrates the full, fixed flow:

  Gmail -> JD Extraction Agent -> JSON Validation -> Normalization ->
  Duplicate Detection -> WhatsApp Formatter -> Policy/Spam Gate ->
  Official Meta WhatsApp API -> Message Tracking

This class owns NO business logic itself — every step delegates to a single
named service, each already independently testable. The orchestrator's only
job is sequencing, persistence checkpoints between steps, and stopping safely
the moment any step can't proceed (never "continue anyway").

Dry-run (`settings.SEND_WHATSAPP=False`, the default) runs every step
including policy evaluation, but stops just short of calling MetaWhatsAppService
so the whole pipeline is exercisable without live WhatsApp credentials.
"""
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.schemas.jd import ExtractedJD, JobStatus, WhatsAppSendStatus
from app.services.gmail_service import GmailService, ParsedEmail
from app.agents.jd_extraction_agent import JDExtractionAgent
from app.services.jd_validation_service import JDValidationService
from app.services.jd_normalization_service import JDNormalizationService
from app.services.jd_duplicate_service import JDDuplicateService
from app.services.whatsapp_formatter import WhatsAppFormatter
from app.services.policy_service import PolicyService
from app.services.meta_whatsapp_service import MetaWhatsAppService
from app.services.message_tracking_service import MessageTrackingService
from app.services.jd_repository import JDRepository

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    gmail_message_id: Optional[str] = None
    job_id: Optional[str] = None
    status: str = "unknown"
    whatsapp_status: Optional[str] = None
    reason: Optional[str] = None
    duplicate_of: Optional[str] = None
    message_preview: Optional[str] = None
    errors: List[str] = field(default_factory=list)


class RecruitmentPipeline:
    def __init__(
        self,
        repository: Optional[JDRepository] = None,
        gmail_service: Optional[GmailService] = None,
        jd_agent: Optional[JDExtractionAgent] = None,
        validation_service: Optional[JDValidationService] = None,
        normalization_service: Optional[JDNormalizationService] = None,
        duplicate_service: Optional[JDDuplicateService] = None,
        formatter: Optional[WhatsAppFormatter] = None,
        policy_service: Optional[PolicyService] = None,
        meta_service: Optional[MetaWhatsAppService] = None,
        tracking_service: Optional[MessageTrackingService] = None,
    ):
        self.repository = repository or JDRepository()
        self.gmail_service = gmail_service or GmailService(repository=self.repository)
        self.jd_agent = jd_agent or JDExtractionAgent()
        self.validation_service = validation_service or JDValidationService()
        self.normalization_service = normalization_service or JDNormalizationService()
        self.duplicate_service = duplicate_service or JDDuplicateService(repository=self.repository)
        self.formatter = formatter or WhatsAppFormatter()
        self.policy_service = policy_service or PolicyService(repository=self.repository)
        self.meta_service = meta_service or MetaWhatsAppService()
        self.tracking_service = tracking_service or MessageTrackingService(repository=self.repository)

    async def run(self, max_results: int = 20) -> List[PipelineResult]:
        """Step 1: pull new Gmail messages not yet processed, run each through
        the full pipeline. One email's failure never aborts the batch."""
        emails = await self.gmail_service.sync_new_emails(max_results=max_results)
        results: List[PipelineResult] = []
        for email in emails:
            try:
                results.append(await self.process_email(email))
            except Exception as exc:
                logger.exception("Unhandled pipeline error for gmail_message_id=%s", email.gmail_message_id)
                results.append(PipelineResult(
                    gmail_message_id=email.gmail_message_id, status="error", errors=[str(exc)],
                ))
                await self.repository.mark_gmail_message_processed(email.gmail_message_id, "error")
        return results

    async def process_email(self, email: ParsedEmail) -> PipelineResult:
        result = PipelineResult(gmail_message_id=email.gmail_message_id)

        # Step 2: dedup by gmail_message_id (defense in depth — GmailService
        # already filters this in sync_new_emails, but process_email may be
        # called directly, e.g. from a test or a manual replay).
        existing = await self.repository.find_job_by_gmail_id(email.gmail_message_id)
        if existing:
            result.job_id = existing["_id"]
            result.status = "already_processed"
            await self.repository.mark_gmail_message_processed(email.gmail_message_id, "already_processed", existing["_id"])
            return result

        # Step 3: create the job record up front (status RECEIVED) so every
        # subsequent failure has somewhere to record itself.
        job_id = await self.repository.create_job({
            "gmail_message_id": email.gmail_message_id,
            "email_subject": email.subject,
            "sender": email.sender,
            "original_email": {
                "subject": email.subject,
                "sender": email.sender,
                "recipient": email.recipient,
                "body": email.body,
                "received_at": email.received_at,
                "attachment_filenames": email.attachment_filenames,
            },
            "status": JobStatus.RECEIVED.value,
            "whatsapp_status": WhatsAppSendStatus.NOT_SENT.value,
        })
        result.job_id = job_id

        # Step 4: JD extraction (text in, JSON out — the LLM never touches
        # anything else in this pipeline).
        raw_jd = await self.jd_agent.extract(email.subject, email.body, email.attachment_text)
        if raw_jd is None:
            await self.repository.update_job(job_id, {"status": JobStatus.FAILED.value, "error": "JD extraction failed or returned no output."})
            await self.repository.mark_gmail_message_processed(email.gmail_message_id, "extraction_failed", job_id)
            result.status = JobStatus.FAILED.value
            result.errors.append("JD extraction failed or returned no output.")
            return result

        await self.repository.update_job(job_id, {"status": JobStatus.EXTRACTED.value, "extracted_jd": raw_jd})

        # Step 5/6: validate (rejects malformed JSON, dangerous content,
        # impossible ranges) — never let unvalidated LLM output past this point.
        validated_jd, errors = self.validation_service.validate(raw_jd)
        if validated_jd is None:
            await self.repository.update_job(job_id, {"status": JobStatus.VALIDATION_FAILED.value, "error": "; ".join(errors)})
            await self.repository.mark_gmail_message_processed(email.gmail_message_id, "validation_failed", job_id)
            result.status = JobStatus.VALIDATION_FAILED.value
            result.errors = errors
            return result

        # Step 7: normalize (skill aliases, employment-type canonicalization,
        # dedup) and compute the deterministic duplicate-detection hash.
        normalized_jd = self.normalization_service.normalize(validated_jd)
        jd_hash = self.normalization_service.compute_hash(normalized_jd)
        await self.repository.update_job(job_id, {
            "normalized_jd": normalized_jd.model_dump(),
            "jd_hash": jd_hash,
        })

        # Step 8: duplicate detection — if seen before, record and stop; never
        # auto-send a repeat.
        dup = await self.duplicate_service.check(jd_hash)
        if dup.is_duplicate:
            await self.repository.update_job(job_id, {
                "status": JobStatus.DUPLICATE.value,
                "is_duplicate_of": dup.existing_job_id,
            })
            await self.repository.mark_gmail_message_processed(email.gmail_message_id, "duplicate", job_id)
            result.status = JobStatus.DUPLICATE.value
            result.duplicate_of = dup.existing_job_id
            return result

        # Step 9: persist as STORED — this JD is now a legitimate, unique job.
        await self.repository.update_job(job_id, {"status": JobStatus.STORED.value})
        job_doc = await self.repository.get_job(job_id)

        # Step 10: deterministic formatting — the LLM never composes the
        # outgoing message.
        message = self.formatter.format(normalized_jd)
        result.message_preview = message

        # Step 11: capability check + policy/spam gate before any send attempt.
        op_supported, unsupported_reason = self.meta_service.check_operation_supported("send_broadcast")
        policy_result = await self.policy_service.check(
            job_doc, message, meta_operation_supported=op_supported, meta_unsupported_reason=unsupported_reason,
        )
        if not policy_result.allowed:
            await self.repository.update_job(job_id, {"whatsapp_status": WhatsAppSendStatus.REJECTED_BY_POLICY.value})
            await self.tracking_service.record_rejection(job_id, None, policy_result.reason, self._policy_reject_status(policy_result.reason))
            await self.repository.mark_gmail_message_processed(email.gmail_message_id, "policy_rejected", job_id)
            result.status = JobStatus.STORED.value
            result.whatsapp_status = WhatsAppSendStatus.REJECTED_BY_POLICY.value
            result.reason = policy_result.reason
            return result

        # Step 12: dry-run gate — everything above (including policy approval)
        # runs identically whether or not we actually send.
        if not settings.SEND_WHATSAPP:
            await self.repository.update_job(job_id, {"whatsapp_status": WhatsAppSendStatus.DRY_RUN.value})
            await self.repository.mark_gmail_message_processed(email.gmail_message_id, "dry_run", job_id)
            result.status = JobStatus.STORED.value
            result.whatsapp_status = WhatsAppSendStatus.DRY_RUN.value
            result.reason = "SEND_WHATSAPP is false — dry-run mode, message approved but not sent."
            return result

        # Step 13: send via the official Meta API (broadcast to configured
        # recipients — see meta_whatsapp_service.py for why this replaces
        # "post to a WhatsApp Group"), then record delivery tracking.
        recipients = [r for r in settings.WHATSAPP_BROADCAST_RECIPIENTS.split(",") if r.strip()]
        api_results = await self.meta_service.send_broadcast(recipients, message)
        any_ok = any(r.ok for r in api_results)
        for api_result in api_results:
            await self.tracking_service.record_result(job_id, api_result.destination, api_result)

        final_ws_status = WhatsAppSendStatus.SENT if any_ok else WhatsAppSendStatus.FAILED
        await self.repository.update_job(job_id, {"whatsapp_status": final_ws_status.value})
        await self.repository.mark_gmail_message_processed(email.gmail_message_id, "sent" if any_ok else "send_failed", job_id)

        result.status = JobStatus.STORED.value
        result.whatsapp_status = final_ws_status.value
        if not any_ok and api_results:
            result.reason = api_results[0].reason
        return result

    @staticmethod
    def _policy_reject_status(reason: Optional[str]):
        from app.schemas.messages import MessageStatus
        if reason and "uplicate" in reason:
            return MessageStatus.DUPLICATE
        if reason and "not supported" in reason.lower():
            return MessageStatus.UNSUPPORTED
        return MessageStatus.REJECTED
