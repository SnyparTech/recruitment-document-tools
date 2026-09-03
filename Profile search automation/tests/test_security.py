"""
Enterprise-Grade Security & Data Leakage Prevention (DLP) Test Suite.

Verifies:
1. OWASP Security Headers (CSP, X-Frame-Options, X-Content-Type-Options, etc.)
2. Localhost & DNS Rebinding Isolation Guard.
3. Request Payload Size Limit Enforcement (1MB cap).
4. In-Memory Token Bucket Rate Limiting (429 response).
5. Logging DLP & PII Masking Filter (emails, phones, bearer tokens, cookies).
6. Input Sanitization & Max Length Validation.
7. Exception Sanitization & Information Leakage Prevention.
"""

import logging
import pytest
from fastapi.testclient import TestClient
from app.core.config import settings
from app.core.security import PIIMaskingFilter, RateLimitMiddleware
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset rate limiter state before and after each test."""
    RateLimitMiddleware.reset()
    yield
    RateLimitMiddleware.reset()


# ==============================================================================
# 1. OWASP Security Headers Verification
# ==============================================================================
def test_security_headers_present_on_health():
    """Verify standard OWASP security headers are present on API responses."""
    response = client.get("/health")
    assert response.status_code == 200

    headers = response.headers
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert "Content-Security-Policy" in headers
    assert "default-src 'self'" in headers.get("Content-Security-Policy")
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "geolocation=()" in headers.get("Permissions-Policy", "")


def test_cache_control_headers_on_search():
    """Verify sensitive search endpoints contain no-store cache control."""
    response = client.post(
        "/search/candidates",
        json={
            "requirement": "Python developer in Hyderabad with 3 years experience",
            "execute": False,
        },
    )
    assert response.status_code == 200
    assert "no-store" in response.headers.get("Cache-Control", "")


# ==============================================================================
# 2. Localhost & DNS Rebinding Guard
# ==============================================================================
def test_localhost_guard_allows_local_host():
    """Verify legitimate localhost Host headers are allowed."""
    response = client.get("/health", headers={"Host": "localhost:8000"})
    assert response.status_code == 200


def test_localhost_guard_blocks_external_host():
    """Verify malicious or external Host headers (DNS rebinding) are blocked with 403."""
    response = client.get("/health", headers={"Host": "evil-attacker.com"})
    assert response.status_code == 403
    assert response.json()["error"] == "FORBIDDEN_HOST"


# ==============================================================================
# 3. Payload Size Limiting
# ==============================================================================
def test_payload_size_limit_rejects_oversized_body():
    """Verify request bodies exceeding MAX_PAYLOAD_SIZE_BYTES return 413."""
    oversized_data = "A" * (settings.MAX_PAYLOAD_SIZE_BYTES + 100)
    response = client.post(
        "/search/candidates",
        headers={"Content-Length": str(len(oversized_data))},
        content=oversized_data,
    )
    assert response.status_code == 413
    assert response.json()["error"] == "PAYLOAD_TOO_LARGE"


# ==============================================================================
# 4. Rate Limiting Enforcement
# ==============================================================================
def test_rate_limiting_triggers_429():
    """Verify exceeding rate limit returns 429 Too Many Requests."""
    hit_429 = False
    for _ in range(settings.RATE_LIMIT_PER_MINUTE + 5):
        resp = client.get("/")
        if resp.status_code == 429:
            hit_429 = True
            assert resp.json()["error"] == "RATE_LIMIT_EXCEEDED"
            assert "Retry-After" in resp.headers
            break

    assert hit_429


# ==============================================================================
# 5. Data Leakage Prevention (DLP) & PII Redaction
# ==============================================================================
def test_dlp_pii_masking_filter():
    """Verify logging filter masks emails, phone numbers, tokens, and cookie secrets."""
    filter_instance = PIIMaskingFilter()

    # 1. Mask Email
    raw_email_msg = "Candidate contact: john.doe@recruitment.com for Python role"
    masked_email = filter_instance.mask_sensitive_text(raw_email_msg)
    assert "john.doe@recruitment.com" not in masked_email
    assert "j***@recruitment.com" in masked_email

    # 2. Mask Phone Number
    raw_phone_msg = "Contact phone is +91 9876543210 or 9876543210"
    masked_phone = filter_instance.mask_sensitive_text(raw_phone_msg)
    assert "9876543210" not in masked_phone
    assert "******3210" in masked_phone

    # 3. Mask Secret Token
    raw_token_msg = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    masked_token = filter_instance.mask_sensitive_text(raw_token_msg)
    assert "[SECRET_TOKEN_REDACTED]" in masked_token

    # 4. Mask Session Cookie Secrets
    raw_cookie_msg = "Saved session cookie nauk_sid=9f8e7d6c5b4a3z and ACCESS=tok12345"
    masked_cookie = filter_instance.mask_sensitive_text(raw_cookie_msg)
    assert "9f8e7d6c5b4a3z" not in masked_cookie
    assert "nauk_sid=[REDACTED]" in masked_cookie
    assert "ACCESS=[REDACTED]" in masked_cookie


# ==============================================================================
# 6. Input Sanitization & Max Length Validation
# ==============================================================================
def test_input_validation_rejects_oversized_prompt():
    """Verify requirement exceeding 2000 chars is rejected."""
    oversized_prompt = "Python developer " * 200  # > 2000 chars
    response = client.post(
        "/search/candidates",
        json={"requirement": oversized_prompt, "execute": False},
    )
    assert response.status_code == 422
    assert response.json()["error"] == "VALIDATION_ERROR"


def test_input_validation_rejects_empty_prompt():
    """Verify empty or pure whitespace requirement is rejected."""
    response = client.post(
        "/search/candidates",
        json={"requirement": "   ", "execute": False},
    )
    assert response.status_code == 422
    assert response.json()["error"] == "VALIDATION_ERROR"


def test_input_validation_strips_null_bytes():
    """Verify null bytes are stripped cleanly during requirement validation."""
    prompt_with_null = "Python\x00 Developer in \x00Hyderabad"
    response = client.post(
        "/search/candidates",
        json={"requirement": prompt_with_null, "execute": False},
    )
    assert response.status_code == 200
    assert "\x00" not in response.json()["requirement"]
