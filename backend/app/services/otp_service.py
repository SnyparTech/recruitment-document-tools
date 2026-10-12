"""
One-time-code email verification for device registration (see
services/device_auth_service.py). Confirms whoever is registering actually
owns the @snypartech.com address they typed, instead of trusting the string
on its own. Codes are short-lived, in-memory only (a backend restart just
means anyone mid-registration has to request a new code — not worth
persisting to disk for a 10-minute-TTL value).

Sends via Outlook/Office365 SMTP (stdlib smtplib — no new dependency).
"""
import logging
import secrets
import smtplib
import socket
import time
from email.mime.text import MIMEText
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

# email -> (code, device_id, expires_at)
_pending: Dict[str, Tuple[str, str, float]] = {}


def _generate_code() -> str:
    return "".join(secrets.choice("0123456789") for _ in range(6))


def send_otp(settings, email: str, device_id: str) -> None:
    """Generates a fresh code, emails it, and stores it pending verification.
    Raises ValueError (safe to show the caller) if SMTP isn't configured or
    the send fails."""
    if not settings.OUTLOOK_EMAIL or not settings.OUTLOOK_PASSWORD:
        raise ValueError("Email verification is not configured on this server.")

    code = _generate_code()
    _pending[email] = (code, device_id, time.time() + settings.DEVICE_OTP_TTL_SECONDS)

    msg = MIMEText(f"Your Snypar Resdex Bot device verification code is: {code}\n\nThis code expires in {settings.DEVICE_OTP_TTL_SECONDS // 60} minutes.")
    msg["Subject"] = "Your device verification code"
    msg["From"] = settings.OUTLOOK_EMAIL
    msg["To"] = email

    try:
        # Resolve to an IPv4 address explicitly and connect to that literal,
        # rather than letting smtplib.SMTP resolve the hostname itself.
        # Containerized hosts (e.g. Render) commonly have no outbound IPv6
        # route; smtp.office365.com has AAAA records, and if getaddrinfo
        # hands back an IPv6 address first, the connection fails immediately
        # with "Network is unreachable" before any SMTP traffic is even
        # attempted — nothing to do with credentials or firewall rules on
        # port 587 itself.
        #
        # Connecting to the IP literal would normally break starttls()'s TLS
        # verification (Office365's cert is issued for the hostname, and
        # smtplib's starttls() uses whatever host you connected with as the
        # SNI/verification name) — so after connecting to the IPv4 address,
        # _host is reset back to the real hostname before starttls() runs,
        # which is what smtplib actually reads for server_hostname.
        addr_info = socket.getaddrinfo(settings.OUTLOOK_SMTP_HOST, settings.OUTLOOK_SMTP_PORT, socket.AF_INET, socket.SOCK_STREAM)
        ipv4_host = addr_info[0][4][0]

        with smtplib.SMTP(timeout=15) as server:
            server.connect(ipv4_host, settings.OUTLOOK_SMTP_PORT)
            server._host = settings.OUTLOOK_SMTP_HOST  # restore for correct TLS hostname verification
            server.starttls()
            server.login(settings.OUTLOOK_EMAIL, settings.OUTLOOK_PASSWORD)
            server.sendmail(settings.OUTLOOK_EMAIL, [email], msg.as_string())
    except Exception as exc:
        _pending.pop(email, None)
        logger.warning("Failed to send device OTP to %s: %s: %s", email, type(exc).__name__, exc)
        raise ValueError("Could not send the verification email. Try again shortly.")


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
