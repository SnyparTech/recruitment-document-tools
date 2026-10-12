"""
Tests for otp_service.py — specifically the IPv4-forcing fix for a real
production bug: Render containers have no outbound IPv6 route, and
smtp.office365.com has AAAA records, so letting smtplib.SMTP resolve the
hostname itself could pick the IPv6 address and fail immediately with
"OSError: [Errno 101] Network is unreachable" (confirmed in prod logs)
before any SMTP traffic was even attempted. The fix resolves IPv4
explicitly, connects to that literal, then restores the real hostname
before starttls() so TLS certificate verification still checks the right
name (Office365's cert is issued for the hostname, not the IP).
"""
import os
import socket
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.services import otp_service


def _settings(**overrides):
    base = dict(
        OUTLOOK_EMAIL="bot@snypartech.com",
        OUTLOOK_PASSWORD="app-password",
        OUTLOOK_SMTP_HOST="smtp.office365.com",
        OUTLOOK_SMTP_PORT=587,
        DEVICE_OTP_TTL_SECONDS=600,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def setup_function(_):
    otp_service._pending.clear()


def test_send_otp_resolves_ipv4_and_connects_to_that_literal_not_the_hostname():
    fake_smtp = MagicMock()
    fake_smtp.__enter__.return_value = fake_smtp

    with patch.object(socket, "getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("40.1.2.3", 587))]) as mock_getaddrinfo, \
         patch("app.services.otp_service.smtplib.SMTP", return_value=fake_smtp) as mock_smtp_cls:
        otp_service.send_otp(_settings(), "harshith@snypartech.com", "device-1")

    mock_getaddrinfo.assert_called_once_with("smtp.office365.com", 587, socket.AF_INET, socket.SOCK_STREAM)
    fake_smtp.connect.assert_called_once_with("40.1.2.3", 587)


def test_send_otp_restores_real_hostname_before_starttls_for_tls_verification():
    """The core correctness requirement: connecting to the IP must not break
    certificate hostname verification — _host must be the real hostname by
    the time starttls() runs, not the IP literal."""
    fake_smtp = MagicMock()
    fake_smtp.__enter__.return_value = fake_smtp
    observed_host_at_starttls = []
    fake_smtp.starttls.side_effect = lambda *a, **kw: observed_host_at_starttls.append(fake_smtp._host)

    with patch.object(socket, "getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("40.1.2.3", 587))]), \
         patch("app.services.otp_service.smtplib.SMTP", return_value=fake_smtp):
        otp_service.send_otp(_settings(), "harshith@snypartech.com", "device-1")

    assert observed_host_at_starttls == ["smtp.office365.com"], \
        "starttls() must see the real hostname for TLS verification, not the IPv4 literal"


def test_send_otp_still_logs_in_and_sends_with_correct_credentials():
    fake_smtp = MagicMock()
    fake_smtp.__enter__.return_value = fake_smtp

    with patch.object(socket, "getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("40.1.2.3", 587))]), \
         patch("app.services.otp_service.smtplib.SMTP", return_value=fake_smtp):
        otp_service.send_otp(_settings(), "harshith@snypartech.com", "device-1")

    fake_smtp.login.assert_called_once_with("bot@snypartech.com", "app-password")
    assert fake_smtp.sendmail.call_args[0][0] == "bot@snypartech.com"
    assert fake_smtp.sendmail.call_args[0][1] == ["harshith@snypartech.com"]


def test_send_otp_stores_pending_entry_for_later_verification():
    fake_smtp = MagicMock()
    fake_smtp.__enter__.return_value = fake_smtp

    with patch.object(socket, "getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("40.1.2.3", 587))]), \
         patch("app.services.otp_service.smtplib.SMTP", return_value=fake_smtp):
        otp_service.send_otp(_settings(), "harshith@snypartech.com", "device-1")

    assert "harshith@snypartech.com" in otp_service._pending


def test_send_otp_raises_value_error_and_cleans_up_on_network_failure():
    """Reproduces the exact prod failure mode: getaddrinfo succeeds but the
    actual connect() raises OSError (unreachable network) — must surface as
    a safe ValueError, not leak the raw OSError, and must not leave a
    dangling pending entry a recruiter could never complete."""
    fake_smtp = MagicMock()
    fake_smtp.__enter__.return_value = fake_smtp
    fake_smtp.connect.side_effect = OSError(101, "Network is unreachable")

    with patch.object(socket, "getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("40.1.2.3", 587))]), \
         patch("app.services.otp_service.smtplib.SMTP", return_value=fake_smtp):
        try:
            otp_service.send_otp(_settings(), "harshith@snypartech.com", "device-1")
            assert False, "expected ValueError"
        except ValueError:
            pass

    assert "harshith@snypartech.com" not in otp_service._pending


def test_send_otp_raises_value_error_when_credentials_not_configured():
    try:
        otp_service.send_otp(_settings(OUTLOOK_EMAIL=None), "harshith@snypartech.com", "device-1")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "not configured" in str(exc)
