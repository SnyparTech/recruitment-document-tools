"""
Tests for the extension device-lock: POST /auth/register-device and the
verify_device dependency applied to the 3 extension-facing /search endpoints
(GET /search/active-plan, POST /search/results, POST /search/plan/live-keywords).
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.services import device_auth_service

client = TestClient(app)


def _reset_device_store(monkeypatch, tmp_path):
    state_file = tmp_path / "authorized_devices.json"
    monkeypatch.setattr(device_auth_service, "_STATE_FILE", str(state_file))
    monkeypatch.setattr(device_auth_service, "_STATE_DIR", str(tmp_path))


def test_lock_disabled_by_default_allows_any_device(monkeypatch, tmp_path):
    _reset_device_store(monkeypatch, tmp_path)
    monkeypatch.setattr(settings, "DEVICE_REGISTRATION_TOKENS", "")
    res = client.get("/search/active-plan")
    assert res.status_code == 200


def test_unregistered_device_rejected_when_lock_enabled(monkeypatch, tmp_path):
    _reset_device_store(monkeypatch, tmp_path)
    monkeypatch.setattr(settings, "DEVICE_REGISTRATION_TOKENS", "tok-abc123")
    res = client.get("/search/active-plan", headers={"X-Device-Id": "some-random-uuid"})
    assert res.status_code == 403


def test_missing_device_id_header_rejected_when_lock_enabled(monkeypatch, tmp_path):
    _reset_device_store(monkeypatch, tmp_path)
    monkeypatch.setattr(settings, "DEVICE_REGISTRATION_TOKENS", "tok-abc123")
    res = client.get("/search/active-plan")
    assert res.status_code == 403


def test_registering_with_valid_token_authorizes_the_device(monkeypatch, tmp_path):
    _reset_device_store(monkeypatch, tmp_path)
    monkeypatch.setattr(settings, "DEVICE_REGISTRATION_TOKENS", "tok-abc123")

    reg = client.post("/auth/register-device", json={"registration_token": "tok-abc123", "device_id": "device-1"})
    assert reg.status_code == 200, reg.text

    res = client.get("/search/active-plan", headers={"X-Device-Id": "device-1"})
    assert res.status_code == 200


def test_token_cannot_be_reused_for_a_second_device(monkeypatch, tmp_path):
    _reset_device_store(monkeypatch, tmp_path)
    monkeypatch.setattr(settings, "DEVICE_REGISTRATION_TOKENS", "tok-abc123")

    first = client.post("/auth/register-device", json={"registration_token": "tok-abc123", "device_id": "device-1"})
    assert first.status_code == 200

    second = client.post("/auth/register-device", json={"registration_token": "tok-abc123", "device_id": "device-2"})
    assert second.status_code == 403

    res = client.get("/search/active-plan", headers={"X-Device-Id": "device-2"})
    assert res.status_code == 403


def test_invalid_token_rejected():
    res = client.post("/auth/register-device", json={"registration_token": "not-a-real-token", "device_id": "device-9"})
    assert res.status_code == 403


def test_jd_upload_endpoint_unaffected_by_device_lock(monkeypatch, tmp_path):
    """The device lock is scoped to the 3 extension-facing endpoints only — the
    frontend dashboard's JD upload/chat endpoints must keep working without a
    device id, even when the lock is enabled."""
    _reset_device_store(monkeypatch, tmp_path)
    monkeypatch.setattr(settings, "DEVICE_REGISTRATION_TOKENS", "tok-abc123")

    res = client.get("/search/plan/chat")
    assert res.status_code == 200
