"""
Tests for otp_service.py — sends the device-registration OTP via Resend's
HTTP API (port 443) instead of raw SMTP. Switched because Render's free web
services block all outbound SMTP traffic (ports 25/465/587) as an
anti-spam policy, confirmed in production logs as both an IPv6-routing
failure and, after that fix, a clean connection timeout on port 587 — an
HTTP API on 443 sidesteps the platform block entirely (the app already
depends on 443 for every LLM provider call).
"""
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import httpx

from app.services import otp_service


def _settings(**overrides):
    base = dict(
        RESEND_API_KEY="re_test_key",
        RESEND_FROM_EMAIL="onboarding@resend.dev",
        DEVICE_OTP_TTL_SECONDS=600,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def setup_function(_):
    otp_service._pending.clear()


@pytest.mark.asyncio
async def test_send_otp_posts_to_resend_with_bearer_auth(monkeypatch):
    captured = {}

    async def fake_post(self, url, json=None, headers=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    await otp_service.send_otp(_settings(), "harshith@snypartech.com", "device-1")

    assert captured["url"] == otp_service.RESEND_API_URL
    assert captured["headers"]["Authorization"] == "Bearer re_test_key"
    assert captured["json"]["to"] == ["harshith@snypartech.com"]
    assert captured["json"]["from"] == "onboarding@resend.dev"
    assert captured["json"]["subject"] == "Your device verification code"


@pytest.mark.asyncio
async def test_send_otp_body_includes_a_6_digit_code_and_the_configured_ttl(monkeypatch):
    captured = {}

    async def fake_post(self, url, json=None, headers=None):
        captured["json"] = json
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    await otp_service.send_otp(_settings(DEVICE_OTP_TTL_SECONDS=300), "harshith@snypartech.com", "device-1")

    stored_code = otp_service._pending["harshith@snypartech.com"][0]
    assert len(stored_code) == 6 and stored_code.isdigit()
    assert stored_code in captured["json"]["text"]
    assert "5 minutes" in captured["json"]["text"]


@pytest.mark.asyncio
async def test_send_otp_stores_pending_entry_for_later_verification(monkeypatch):
    async def fake_post(self, url, json=None, headers=None):
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    await otp_service.send_otp(_settings(), "harshith@snypartech.com", "device-1")

    assert "harshith@snypartech.com" in otp_service._pending


@pytest.mark.asyncio
async def test_send_otp_raises_value_error_on_resend_error_response(monkeypatch):
    async def fake_post(self, url, json=None, headers=None):
        return httpx.Response(422, json={"message": "invalid from address"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    with pytest.raises(ValueError):
        await otp_service.send_otp(_settings(), "harshith@snypartech.com", "device-1")

    assert "harshith@snypartech.com" not in otp_service._pending, "a failed send must not leave a dangling pending entry"


@pytest.mark.asyncio
async def test_send_otp_raises_value_error_on_network_failure(monkeypatch):
    """Reproduces the exact prod failure mode: the HTTP request itself fails
    (timeout/connection error) — must surface as a safe ValueError, not a
    raw httpx exception, and must not leave a dangling pending entry."""
    async def fake_post(self, url, json=None, headers=None):
        raise httpx.ConnectTimeout("timed out")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    with pytest.raises(ValueError):
        await otp_service.send_otp(_settings(), "harshith@snypartech.com", "device-1")

    assert "harshith@snypartech.com" not in otp_service._pending


@pytest.mark.asyncio
async def test_send_otp_raises_value_error_when_not_configured():
    with pytest.raises(ValueError, match="not configured"):
        await otp_service.send_otp(_settings(RESEND_API_KEY=None), "harshith@snypartech.com", "device-1")


def test_verify_otp_accepts_correct_code():
    otp_service._pending["harshith@snypartech.com"] = ("123456", "device-1", 9999999999.0)
    otp_service.verify_otp("harshith@snypartech.com", "device-1", "123456")
    assert "harshith@snypartech.com" not in otp_service._pending, "a verified code must be consumed"


def test_verify_otp_rejects_wrong_code():
    otp_service._pending["harshith@snypartech.com"] = ("123456", "device-1", 9999999999.0)
    with pytest.raises(ValueError, match="Incorrect"):
        otp_service.verify_otp("harshith@snypartech.com", "device-1", "000000")


def test_verify_otp_rejects_expired_code():
    otp_service._pending["harshith@snypartech.com"] = ("123456", "device-1", 1.0)
    with pytest.raises(ValueError, match="expired"):
        otp_service.verify_otp("harshith@snypartech.com", "device-1", "123456")


def test_verify_otp_rejects_mismatched_device():
    otp_service._pending["harshith@snypartech.com"] = ("123456", "device-1", 9999999999.0)
    with pytest.raises(ValueError, match="different device"):
        otp_service.verify_otp("harshith@snypartech.com", "device-2", "123456")
