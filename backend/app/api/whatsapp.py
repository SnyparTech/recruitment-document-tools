import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.schemas.jd import ExtractedJD, WhatsAppSendStatus
from app.schemas.whatsapp import (
    PolicyCheckResult,
    WhatsAppCheckRequest,
    WhatsAppPreviewRequest,
    WhatsAppPreviewResponse,
    WhatsAppSendRequest,
)
from app.services.jd_repository import JDRepository
from app.services.whatsapp_formatter import WhatsAppFormatter
from app.services.policy_service import PolicyService
from app.services.meta_whatsapp_service import MetaWhatsAppService
from app.services.message_tracking_service import MessageTrackingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/whatsapp", tags=["WhatsApp"])

_repository = JDRepository()
_formatter = WhatsAppFormatter()
_policy_service = PolicyService(repository=_repository)
_meta_service = MetaWhatsAppService()
_tracking_service = MessageTrackingService(repository=_repository)


async def _resolve_jd(job_id: Optional[str], extracted_jd: Optional[dict]) -> tuple[Optional[ExtractedJD], Optional[dict]]:
    """Returns (jd_model, job_doc). job_doc is None when previewing an inline dict."""
    if job_id:
        job = await _repository.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={
                "error": "JOB_NOT_FOUND", "message": f"No job found with id {job_id}.",
            })
        jd_dict = job.get("normalized_jd") or job.get("extracted_jd")
        if not jd_dict:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
                "error": "JD_NOT_AVAILABLE", "message": "This job has no extracted/normalized JD to format.",
            })
        return ExtractedJD.model_validate(jd_dict), job
    if extracted_jd:
        return ExtractedJD.model_validate(extracted_jd), None
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
        "error": "MISSING_INPUT", "message": "Provide either job_id or extracted_jd.",
    })


@router.post("/preview", response_model=WhatsAppPreviewResponse, summary="Format a JD into a WhatsApp message without sending")
async def preview_whatsapp(request: WhatsAppPreviewRequest):
    jd, _job = await _resolve_jd(request.job_id, request.extracted_jd)
    message = _formatter.format(jd)
    return WhatsAppPreviewResponse(message=message, char_count=len(message))


@router.post("/check", response_model=PolicyCheckResult, summary="Run the policy/spam gate for a stored job (no send)")
async def check_whatsapp(request: WhatsAppCheckRequest):
    jd, job = await _resolve_jd(request.job_id, None)
    message = _formatter.format(jd)
    op_supported, unsupported_reason = _meta_service.check_operation_supported("send_broadcast")
    return await _policy_service.check(job, message, meta_operation_supported=op_supported, meta_unsupported_reason=unsupported_reason)


@router.post("/send", summary="Send a stored job's WhatsApp message via the official Meta API (subject to policy + dry-run)")
async def send_whatsapp(request: WhatsAppSendRequest):
    jd, job = await _resolve_jd(request.job_id, None)
    message = _formatter.format(jd)

    op_supported, unsupported_reason = _meta_service.check_operation_supported("send_broadcast")
    policy_result = await _policy_service.check(job, message, meta_operation_supported=op_supported, meta_unsupported_reason=unsupported_reason)
    if not policy_result.allowed:
        await _repository.update_job(request.job_id, {"whatsapp_status": WhatsAppSendStatus.REJECTED_BY_POLICY.value})
        return {"sent": False, "status": "rejected_by_policy", "reason": policy_result.reason, "checks_run": policy_result.checks_run}

    if not settings.SEND_WHATSAPP:
        await _repository.update_job(request.job_id, {"whatsapp_status": WhatsAppSendStatus.DRY_RUN.value})
        return {
            "sent": False,
            "status": "dry_run",
            "reason": "SEND_WHATSAPP is false — message approved by policy but not sent. Set SEND_WHATSAPP=true to enable live sending.",
            "message_preview": message,
        }

    if settings.META_GROUP_ID:
        group_result = await _meta_service.send_to_group(settings.META_GROUP_ID, message)
        api_results = [group_result]
    else:
        recipients = [r for r in settings.WHATSAPP_BROADCAST_RECIPIENTS.split(",") if r.strip()]
        api_results = await _meta_service.send_broadcast(recipients, message)

    any_ok = any(r.ok for r in api_results)
    for api_result in api_results:
        await _tracking_service.record_result(request.job_id, api_result.destination, api_result)

    final_status = WhatsAppSendStatus.SENT if any_ok else WhatsAppSendStatus.FAILED
    await _repository.update_job(request.job_id, {"whatsapp_status": final_status.value})
    return {
        "sent": any_ok,
        "status": final_status.value,
        "results": [r.model_dump() for r in api_results],
    }


# ─── WhatsApp Group management (requires OBA-approved account — see
# meta_whatsapp_service.py module docstring) ──────────────────────────────


class CreateGroupRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = Field(default=None, max_length=2048)
    join_approval_mode: Optional[str] = Field(default=None, description='"auto_approve" or "approval_required"')


@router.post("/groups", summary="Create a new WhatsApp group owned by this business account")
async def create_group(request: CreateGroupRequest):
    result = await _meta_service.create_group(request.subject, request.description, request.join_approval_mode)
    if not result["ok"]:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=result["reason"])
    return result["data"]


@router.get("/groups", summary="List WhatsApp groups this business account owns")
async def list_groups(limit: int = 25, after: Optional[str] = None, before: Optional[str] = None):
    result = await _meta_service.list_groups(limit=limit, after=after, before=before)
    if not result["ok"]:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=result["reason"])
    return result["data"]


@router.get("/groups/{group_id}", summary="Get a WhatsApp group's details")
async def get_group(group_id: str, fields: Optional[str] = None):
    result = await _meta_service.get_group(group_id, fields=fields)
    if not result["ok"]:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=result["reason"])
    return result["data"]


@router.get("/groups/{group_id}/invite-link", summary="Get the invite link for a group this business account owns")
async def get_group_invite_link(group_id: str):
    result = await _meta_service.get_invite_link(group_id)
    if not result["ok"]:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=result["reason"])
    return result["data"]
