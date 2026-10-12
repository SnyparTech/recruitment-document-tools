"""
One-time-code email verification for device registration (see
services/device_auth_service.py). Confirms whoever is registering actually
owns the @snypartech.com address they typed, instead of trusting the string
on its own. Codes are short-lived, in-memory only (a backend restart just
means anyone mid-registration has to request a new code — not worth
persisting to disk for a 10-minute-TTL value).

Sends via Resend's HTTP API (https://api.resend.com/emails, port 443) —
NOT raw SMTP. Render's free web services block outbound SMTP (ports 25,
465, 587) entirely as an anti-spam policy, confirmed in production logs as
TimeoutError/OSError against smtp.office365.com. HTTPS on 443 is never
blocked (the app already depends on it for every LLM provider call), so an
HTTP-based email API sidesteps the problem instead of fighting the platform.

Setup requirement: RESEND_FROM_EMAIL's domain must be verified in Resend's
dashboard (Domains -> Add Domain, then add the SPF/DKIM DNS records it
gives you) before this can email anyone other than the Resend account
owner — Resend's default onboarding@resend.dev sender only delivers to the
account owner's own address until a real domain is verified.
"""
import logging
import secrets
import time
from typing import Dict, Tuple

import httpx

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"

# email -> (code, device_id, expires_at)
_pending: Dict[str, Tuple[str, str, float]] = {}


def _generate_code() -> str:
    return "".join(secrets.choice("0123456789") for _ in range(6))


async def send_otp(settings, email: str, device_id: str) -> None:
    """Generates a fresh code, emails it via Resend, and stores it pending
    verification. Raises ValueError (safe to show the caller) if Resend
    isn't configured or the send fails."""
    if not settings.RESEND_API_KEY:
        raise ValueError("Email verification is not configured on this server.")

    code = _generate_code()
    _pending[email] = (code, device_id, time.time() + settings.DEVICE_OTP_TTL_SECONDS)

    payload = {
        "from": settings.RESEND_FROM_EMAIL,
        "to": [email],
        "subject": "Your device verification code",
        "text": f"Your Snypar Resdex Bot device verification code is: {code}\n\nThis code expires in {settings.DEVICE_OTP_TTL_SECONDS // 60} minutes.",
    }
    headers = {"Authorization": f"Bearer {settings.RESEND_API_KEY}", "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(RESEND_API_URL, json=payload, headers=headers)
        if response.status_code >= 400:
            # Never log the API key (it's in `headers`, not touched here);
            # Resend's error body is safe to log — no PII beyond the
            # recipient email, which is already in the surrounding log line.
            logger.warning("Resend send failed for %s: HTTP %d: %s", email, response.status_code, response.text[:300])
            raise ValueError("Could not send the verification email. Try again shortly.")
    except httpx.HTTPError as exc:
        _pending.pop(email, None)
        logger.warning("Failed to send device OTP to %s: %s: %s", email, type(exc).__name__, exc)
        raise ValueError("Could not send the verification email. Try again shortly.")
    except ValueError:
        _pending.pop(email, None)
        raise


def verify_otp(email: str, device_id: str, code: str) -> None:
    """Raises ValueError (safe to show the caller) if the code is missing,
    expired, for a different device, or wrong. On success, consumes it."""
    entry = _pending.get(email)
    if not entry:
        raise ValueError("No verification code was requested for this email. Request a new one.")

    expected_code, expected_device_id, expires_at = entry
    if time.time() > expires_at:
        _pending.pop(email, None)
        raise ValueError("This code has expired. Request a new one.")
    if device_id != expected_device_id:
        raise ValueError("Code was requested from a different device. Request a new one.")
    if not secrets.compare_digest(code.strip(), expected_code):
        raise ValueError("Incorrect code.")

    _pending.pop(email, None)
