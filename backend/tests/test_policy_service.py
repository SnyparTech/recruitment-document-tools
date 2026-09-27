from unittest.mock import AsyncMock

import pytest

from app.core.config import settings
from app.schemas.jd import JobStatus, WhatsAppSendStatus
from app.services.policy_service import PolicyService


def _job(**overrides):
    doc = {
        "_id": "job1",
        "status": JobStatus.STORED.value,
        "whatsapp_status": WhatsAppSendStatus.NOT_SENT.value,
        "is_duplicate_of": None,
    }
    doc.update(overrides)
    return doc


def _make_service(sent_count=0):
    repo = AsyncMock()
    repo.count_messages_sent_since.return_value = sent_count
    return PolicyService(repository=repo), repo


@pytest.fixture(autouse=True)
def _configured_meta(monkeypatch):
    monkeypatch.setattr(settings, "META_ACCESS_TOKEN", "token")
    monkeypatch.setattr(settings, "META_PHONE_NUMBER_ID", "12345")
    monkeypatch.setattr(settings, "WHATSAPP_BROADCAST_RECIPIENTS", "+911234567890")
    monkeypatch.setattr(settings, "WHATSAPP_MAX_MESSAGES_PER_HOUR", 20)
    monkeypatch.setattr(settings, "WHATSAPP_MESSAGE_MAX_CHARS", 4096)


async def test_all_checks_pass_allows_send():
    service, _ = _make_service()
    result = await service.check(_job(), "hello world", meta_operation_supported=True)
    assert result.allowed is True
    assert result.reason is None


async def test_validation_failed_job_denied():
    service, _ = _make_service()
    result = await service.check(_job(status=JobStatus.VALIDATION_FAILED.value), "msg", meta_operation_supported=True)
    assert result.allowed is False
    assert "jd_valid" in result.checks_run


async def test_empty_message_denied():
    service, _ = _make_service()
    result = await service.check(_job(), "   ", meta_operation_supported=True)
    assert result.allowed is False
    assert result.reason == "Formatted WhatsApp message is empty."


async def test_message_too_long_denied(monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_MESSAGE_MAX_CHARS", 10)
    service, _ = _make_service()
    result = await service.check(_job(), "x" * 50, meta_operation_supported=True)
    assert result.allowed is False
    assert "exceeds" in result.reason


async def test_duplicate_job_denied():
    service, _ = _make_service()
    result = await service.check(_job(status=JobStatus.DUPLICATE.value), "msg", meta_operation_supported=True)
    assert result.allowed is False
    assert "Duplicate" in result.reason


async def test_already_sent_denied():
    service, _ = _make_service()
    result = await service.check(_job(whatsapp_status=WhatsAppSendStatus.SENT.value), "msg", meta_operation_supported=True)
    assert result.allowed is False


async def test_rate_limit_exceeded_denied():
    service, _ = _make_service(sent_count=20)
    result = await service.check(_job(), "msg", meta_operation_supported=True)
    assert result.allowed is False
    assert "limit" in result.reason.lower()


async def test_rate_limit_query_failure_fails_closed():
    repo = AsyncMock()
    repo.count_messages_sent_since.side_effect = RuntimeError("db down")
    service = PolicyService(repository=repo)
    result = await service.check(_job(), "msg", meta_operation_supported=True)
    assert result.allowed is False
    assert "fail-closed" in result.reason


async def test_missing_meta_config_denied(monkeypatch):
    monkeypatch.setattr(settings, "META_ACCESS_TOKEN", "")
    service, _ = _make_service()
    result = await service.check(_job(), "msg", meta_operation_supported=True)
    assert result.allowed is False
    assert "meta_config_present" in result.checks_run


async def test_missing_destination_denied(monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_BROADCAST_RECIPIENTS", "")
    service, _ = _make_service()
    result = await service.check(_job(), "msg", meta_operation_supported=True)
    assert result.allowed is False
    assert "destination_configured" in result.checks_run


async def test_unsupported_meta_operation_denied():
    service, _ = _make_service()
    result = await service.check(
        _job(), "msg", meta_operation_supported=False, meta_unsupported_reason="No group endpoint exists."
    )
    assert result.allowed is False
    assert result.reason == "No group endpoint exists."
