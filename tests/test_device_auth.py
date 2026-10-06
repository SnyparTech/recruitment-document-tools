"""
Tests for the extension device-lock: OTP-verified registration
(POST /auth/request-device-otp, POST /auth/register-device) gated by
@snypartech.com email, one device per email, and the verify_device
dependency applied to the 3 extension-facing /search endpoints
(GET /search/active-plan, POST /search/results, POST /search/plan/live-keywords).
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.services import device_auth_service, otp_service

client = TestClient(app)


def _reset_device_store(monkeypatch, tmp_path):
    state_file = tmp_path / "authorized_devices.json"
    monkeypatch.setattr(device_auth_service, "_STATE_FILE", str(state_file))
    monkeypatch.setattr(device_auth_service, "_STATE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "DEVICE_AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "AUTHORIZED_EMAIL_DOMAIN", "snypartech.com")
    otp_service._pending.clear()


def _stub_send_otp(monkeypatch, captured):
    def fake_send(settings, email, device_id):
        code = "123456"
        otp_service._pending[email] = (code, device_id, __import__("time").time() + 600)
        captured["code"] = code
    monkeypatch.setattr(otp_service, "send_otp", fake_send)


def test_lock_disabled_allows_any_device(monkeypatch, tmp_path):
    _reset_device_store(monkeypatch, tmp_path)
    monkeypatch.setattr(settings, "DEVICE_AUTH_ENABLED", False)
    res = client.get("/search/active-plan")
    assert res.status_code == 200


def test_unregistered_device_rejected_when_lock_enabled(monkeypatch, tmp_path):
    _reset_device_store(monkeypatch, tmp_path)
    res = client.get("/search/active-plan", headers={"X-Device-Id": "some-random-uuid"})
    assert res.status_code == 403


def test_missing_device_id_header_rejected_when_lock_enabled(monkeypatch, tmp_path):
    _reset_device_store(monkeypatch, tmp_path)
    res = client.get("/search/active-plan")
    assert res.status_code == 403


def test_non_company_email_rejected_at_otp_request(monkeypatch, tmp_path):
    _reset_device_store(monkeypatch, tmp_path)
    res = client.post("/auth/request-device-otp", json={"email": "someone@gmail.com", "device_id": "device-1"})
    assert res.status_code == 403


def test_register_without_requesting_otp_first_is_rejected(monkeypatch, tmp_path):
    _reset_device_store(monkeypatch, tmp_path)
    res = client.post("/auth/register-device", json={"email": "harshith@snypartech.com", "device_id": "device-1", "otp": "000000"})
    assert res.status_code == 403


def test_wrong_otp_rejected(monkeypatch, tmp_path):
    _reset_device_store(monkeypatch, tmp_path)
    captured = {}
    _stub_send_otp(monkeypatch, captured)

    req = client.post("/auth/request-device-otp", json={"email": "harshith@snypartech.com", "device_id": "device-1"})
    assert req.status_code == 200

    res = client.post("/auth/register-device", json={"email": "harshith@snypartech.com", "device_id": "device-1", "otp": "999999"})
    assert res.status_code == 403


def test_correct_otp_authorizes_the_device(monkeypatch, tmp_path):
    _reset_device_store(monkeypatch, tmp_path)
    captured = {}
    _stub_send_otp(monkeypatch, captured)

    req = client.post("/auth/request-device-otp", json={"email": "harshith@snypartech.com", "device_id": "device-1"})
    assert req.status_code == 200

    res = client.post("/auth/register-device", json={"email": "harshith@snypartech.com", "device_id": "device-1", "otp": captured["code"]})
    assert res.status_code == 200, res.text

    check = client.get("/search/active-plan", headers={"X-Device-Id": "device-1"})
    assert check.status_code == 200


def test_otp_is_single_use(monkeypatch, tmp_path):
    _reset_device_store(monkeypatch, tmp_path)
    captured = {}
    _stub_send_otp(monkeypatch, captured)

    client.post("/auth/request-device-otp", json={"email": "harshith@snypartech.com", "device_id": "device-1"})
    first = client.post("/auth/register-device", json={"email": "harshith@snypartech.com", "device_id": "device-1", "otp": captured["code"]})
    assert first.status_code == 200

    second = client.post("/auth/register-device", json={"email": "harshith@snypartech.com", "device_id": "device-1", "otp": captured["code"]})
    assert second.status_code == 403


def test_same_email_cannot_register_a_second_device(monkeypatch, tmp_path):
    _reset_device_store(monkeypatch, tmp_path)
    captured = {}
    _stub_send_otp(monkeypatch, captured)

    client.post("/auth/request-device-otp", json={"email": "harshith@snypartech.com", "device_id": "device-1"})
    first = client.post("/auth/register-device", json={"email": "harshith@snypartech.com", "device_id": "device-1", "otp": captured["code"]})
    assert first.status_code == 200

    client.post("/auth/request-device-otp", json={"email": "harshith@snypartech.com", "device_id": "device-2"})
    second = client.post("/auth/register-device", json={"email": "harshith@snypartech.com", "device_id": "device-2", "otp": captured["code"]})
    assert second.status_code == 403

    res = client.get("/search/active-plan", headers={"X-Device-Id": "device-2"})
    assert res.status_code == 403


def test_jd_upload_endpoint_unaffected_by_device_lock(monkeypatch, tmp_path):
    """The device lock is scoped to the 3 extension-facing endpoints only — the
    frontend dashboard's JD upload/chat endpoints must keep working without a
    device id, even when the lock is enabled."""
    _reset_device_store(monkeypatch, tmp_path)
    res = client.get("/search/plan/chat")
    assert res.status_code == 200
