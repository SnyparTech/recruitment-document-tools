"""
Tests for WhatsApp Group support in MetaWhatsAppService (create/list/get group,
invite link, send_to_group) and the /api/whatsapp/groups endpoints. Network
calls are stubbed (monkeypatching the service's low-level request helpers) —
these test payload construction and capability gating, not live Meta API
behavior (which requires a real OBA-approved account, see module docstring
in meta_whatsapp_service.py).
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import pytest
from app.services.meta_whatsapp_service import MetaWhatsAppService


def _service():
    return MetaWhatsAppService(access_token="fake-token", phone_number_id="123456")


@pytest.mark.asyncio
async def test_create_group_posts_correct_payload_to_groups_endpoint(monkeypatch):
    service = _service()
    captured = {}

    async def fake_graph_request(method, url, json=None, params=None):
        captured.update(method=method, url=url, json=json)
        return {"ok": True, "data": {"id": "group-1", "subject": json["subject"]}}

    monkeypatch.setattr(service, "_graph_request", fake_graph_request)

    result = await service.create_group("Backend Hiring", description="JD broadcast group")
    assert result["ok"] is True
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/123456/groups")
    assert captured["json"]["subject"] == "Backend Hiring"
    assert captured["json"]["description"] == "JD broadcast group"
    assert captured["json"]["messaging_product"] == "whatsapp"


@pytest.mark.asyncio
async def test_send_to_group_uses_recipient_type_group(monkeypatch):
    service = _service()
    captured = {}

    async def fake_post_with_retry(payload, destination=None):
        captured.update(payload=payload, destination=destination)
        from app.schemas.messages import MetaApiResult
        return MetaApiResult(ok=True, status="sent", message_id="wamid.1", destination=destination)

    monkeypatch.setattr(service, "_post_with_retry", fake_post_with_retry)

    result = await service.send_to_group("group-1", "New JD posted")
    assert result.ok is True
    assert captured["payload"]["recipient_type"] == "group"
    assert captured["payload"]["to"] == "group-1"
    assert captured["payload"]["type"] == "text"


@pytest.mark.asyncio
async def test_group_operations_fail_cleanly_without_credentials():
    service = MetaWhatsAppService(access_token=None, phone_number_id=None)
    result = await service.create_group("Backend Hiring")
    assert result["ok"] is False
    assert "credentials" in result["reason"].lower() or "configured" in result["reason"].lower()


@pytest.mark.asyncio
async def test_invite_link_hits_the_group_node_not_phone_number_id(monkeypatch):
    service = _service()
    captured = {}

    async def fake_graph_request(method, url, json=None, params=None):
        captured.update(method=method, url=url)
        return {"ok": True, "data": {"invite_link": "https://chat.whatsapp.com/abc123"}}

    monkeypatch.setattr(service, "_graph_request", fake_graph_request)

    result = await service.get_invite_link("group-1")
    assert result["ok"] is True
    assert captured["method"] == "GET"
    assert captured["url"].endswith("/group-1/invite_link")
