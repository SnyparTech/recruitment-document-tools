"""
Tests for the website-login + extension-pairing auth system that replaced
the extension's old standalone email+OTP device-registration flow:

- POST /auth/login/request-otp, POST /auth/login/verify -> HttpOnly session
  cookie, gated by @snypartech.com email (same rule as before).
- GET /auth/me, POST /auth/logout.
- POST /auth/pairing-code (requires a logged-in session) -> short-lived code.
- POST /auth/pair-device (exchanges a pairing code for a long-lived device
  token) -> used by the 3 extension-facing /search endpoints via
  verify_device (GET /search/active-plan, POST /search/results,
  POST /search/plan/live-keywords).
- verify_website_session gates every other /search endpoint.

All three new Mongo-backed services (web_session_service, pairing_service,
device_token_service) are swapped for an in-memory fake collection — no real
MongoDB needed, same reasoning as test_preference_service.py's FakeCollection.
"""
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.services import device_token_service, otp_service, pairing_service, web_session_service

# https base_url (not the default http://testserver) — the session cookie is
# Secure+SameSite=None (required for the real cross-origin Vercel/extension
# setup), and httpx's cookie jar won't send a Secure cookie back over http.
client = TestClient(app, base_url="https://testserver")


class FakeCollection:
    """Minimal sync in-memory double for the handful of pymongo operations
    these services actually use."""

    def __init__(self):
        self.docs = {}

    def insert_one(self, doc):
        self.docs[doc["_id"]] = dict(doc)

    def find_one(self, filter_):
        doc = self.docs.get(filter_.get("_id"))
        if doc is None:
            return None
        expires_at = filter_.get("expires_at")
        if expires_at and not (doc.get("expires_at", 0) > expires_at["$gt"]):
            return None
        return dict(doc)

    def find_one_and_delete(self, filter_):
        doc = self.find_one(filter_)
        if doc is not None:
            self.docs.pop(filter_["_id"], None)
        return doc

    def update_one(self, filter_, update):
        doc = self.docs.get(filter_.get("_id"))
        if doc is not None:
            doc.update(update.get("$set", {}))

    def delete_one(self, filter_):
        self.docs.pop(filter_.get("_id"), None)

    def replace_one(self, filter_, doc, upsert=False):
        self.docs[filter_["_id"]] = dict(doc)


def _reset_auth(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "AUTHORIZED_EMAIL_DOMAIN", "snypartech.com")
    web_coll, pairing_coll, device_coll = FakeCollection(), FakeCollection(), FakeCollection()
    monkeypatch.setattr(web_session_service, "_get_collection", lambda: web_coll)
    monkeypatch.setattr(pairing_service, "_get_collection", lambda: pairing_coll)
    monkeypatch.setattr(device_token_service, "_get_collection", lambda: device_coll)
    otp_service._pending.clear()
    client.cookies.clear()


def _stub_send_otp(monkeypatch, captured):
    async def fake_send(settings, email, device_id):
        code = "123456"
        otp_service._pending[email] = (code, device_id, time.time() + 600)
        captured["code"] = code
    monkeypatch.setattr(otp_service, "send_otp", fake_send)


def _login(monkeypatch, email="harshith@snypartech.com"):
    captured = {}
    _stub_send_otp(monkeypatch, captured)
    req = client.post("/auth/login/request-otp", json={"email": email})
    assert req.status_code == 200, req.text
    res = client.post("/auth/login/verify", json={"email": email, "otp": captured["code"]})
    assert res.status_code == 200, res.text
    return res


def test_auth_disabled_allows_any_extension_request(monkeypatch):
    _reset_auth(monkeypatch)
    monkeypatch.setattr(settings, "AUTH_ENABLED", False)
    res = client.get("/search/active-plan")
    assert res.status_code == 200


def test_me_reports_auth_disabled(monkeypatch):
    _reset_auth(monkeypatch)
    monkeypatch.setattr(settings, "AUTH_ENABLED", False)
    res = client.get("/auth/me")
    assert res.status_code == 200
    assert res.json() == {"status": "success", "auth_enabled": False, "email": None}


def test_website_endpoint_rejected_without_session_when_auth_enabled(monkeypatch):
    _reset_auth(monkeypatch)
    res = client.get("/search/plan/chat")
    assert res.status_code == 401


def test_extension_endpoint_rejected_without_device_token_when_auth_enabled(monkeypatch):
    _reset_auth(monkeypatch)
    res = client.get("/search/active-plan", headers={"X-Device-Id": "some-device"})
    assert res.status_code == 403


def test_non_company_email_rejected_at_login_otp_request(monkeypatch):
    _reset_auth(monkeypatch)
    res = client.post("/auth/login/request-otp", json={"email": "someone@gmail.com"})
    assert res.status_code == 403


def test_wrong_otp_rejected_at_login(monkeypatch):
    _reset_auth(monkeypatch)
    captured = {}
    _stub_send_otp(monkeypatch, captured)
    client.post("/auth/login/request-otp", json={"email": "harshith@snypartech.com"})
    res = client.post("/auth/login/verify", json={"email": "harshith@snypartech.com", "otp": "999999"})
    assert res.status_code == 403


def test_login_sets_cookie_and_unlocks_website_endpoints(monkeypatch):
    _reset_auth(monkeypatch)
    _login(monkeypatch)

    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json() == {"status": "success", "auth_enabled": True, "email": "harshith@snypartech.com"}

    res = client.get("/search/plan/chat")
    assert res.status_code == 200


def test_logout_locks_website_endpoints_again(monkeypatch):
    _reset_auth(monkeypatch)
    _login(monkeypatch)

    out = client.post("/auth/logout")
    assert out.status_code == 200

    res = client.get("/search/plan/chat")
    assert res.status_code == 401


def test_pairing_code_requires_login(monkeypatch):
    _reset_auth(monkeypatch)
    res = client.post("/auth/pairing-code")
    assert res.status_code == 401


def test_pairing_code_pair_device_and_extension_endpoints_unlock(monkeypatch):
    _reset_auth(monkeypatch)
    _login(monkeypatch)

    code_res = client.post("/auth/pairing-code")
    assert code_res.status_code == 200, code_res.text
    code = code_res.json()["code"]

    pair_res = client.post("/auth/pair-device", json={"code": code, "device_id": "device-1"})
    assert pair_res.status_code == 200, pair_res.text
    device_token = pair_res.json()["device_token"]

    check = client.get(
        "/search/active-plan",
        headers={"X-Device-Id": "device-1", "X-Device-Token": device_token},
    )
    assert check.status_code == 200


def test_pairing_code_is_single_use(monkeypatch):
    _reset_auth(monkeypatch)
    _login(monkeypatch)

    code = client.post("/auth/pairing-code").json()["code"]
    first = client.post("/auth/pair-device", json={"code": code, "device_id": "device-1"})
    assert first.status_code == 200

    second = client.post("/auth/pair-device", json={"code": code, "device_id": "device-2"})
    assert second.status_code == 403


def test_wrong_device_token_rejected(monkeypatch):
    _reset_auth(monkeypatch)
    _login(monkeypatch)

    code = client.post("/auth/pairing-code").json()["code"]
    client.post("/auth/pair-device", json={"code": code, "device_id": "device-1"})

    res = client.get(
        "/search/active-plan",
        headers={"X-Device-Id": "device-1", "X-Device-Token": "not-the-real-token"},
    )
    assert res.status_code == 403


def test_jd_upload_endpoint_requires_login_when_auth_enabled(monkeypatch):
    """The split between the website router (login-gated) and the device
    router (device-token-gated) must put the chat/draft endpoints on the
    website side."""
    _reset_auth(monkeypatch)
    res = client.get("/search/plan/chat")
    assert res.status_code == 401
    _login(monkeypatch)
    res = client.get("/search/plan/chat")
    assert res.status_code == 200
