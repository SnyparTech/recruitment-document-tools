"""
Shared email-domain gating for website login (api/device_auth.py's
/auth/login/* routes) — must end @<AUTHORIZED_EMAIL_DOMAIN>, default
snypartech.com. The actual auth state (sessions, pairing codes, device
tokens) lives in web_session_service.py / pairing_service.py /
device_token_service.py (MongoDB-backed); this module is just the one
validation rule shared by the login flow.
"""
import re

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_and_validate_email(settings, email: str) -> str:
    """Raises ValueError (safe to show the caller) for a malformed address or
    one outside AUTHORIZED_EMAIL_DOMAIN. Returns the normalized (lowercased,
    trimmed) address otherwise. Deliberately gives the same generic rejection
    for both cases — doesn't confirm/deny which rule failed, so a wrong-domain
    guess can't be used to probe for valid-looking addresses."""
    email = (email or "").strip().lower()
    domain = (getattr(settings, "AUTHORIZED_EMAIL_DOMAIN", "") or "").strip().lower()
    valid_format = bool(_EMAIL_RE.match(email))
    valid_domain = not domain or email.endswith("@" + domain)
    if not valid_format or not valid_domain:
        suffix = f" with an @{domain} email address" if domain else ""
        raise ValueError(f"Enter a valid company email{suffix}.")
    return email
