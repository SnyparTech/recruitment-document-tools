"""
FastAPI dependency gating the website itself (recruiter login), as opposed
to core/device_auth.py which gates the Chrome extension's own requests.
Apply via `dependencies=[Depends(verify_website_session)]` on a router —
currently the whole /search router except its 3 extension-only endpoints
(see api/search.py, which splits those onto a separate router using
verify_device instead).

FAIL-CLOSED: unlike most of this codebase's "best effort" services
(preference_service.py, state_persistence.py — a Mongo hiccup there just
silently no-ops a non-critical feature), auth is a security boundary. If
web_session_service can't reach its backing store, this raises 503, not a
401/"not logged in" bypass — an infra outage must never look like "let them
through."
"""
from fastapi import Cookie, HTTPException, status
from typing import Optional

from app.core.config import settings
from app.services import web_session_service

SESSION_COOKIE_NAME = "web_session"


async def verify_website_session(
    web_session: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> Optional[str]:
    """Returns the logged-in email, or None if AUTH_ENABLED is off (the
    admin has deliberately not turned this on yet — distinct from a missing
    session, which is rejected below)."""
    if not getattr(settings, "AUTH_ENABLED", False):
        return None

    try:
        email = web_session_service.get_session_email(web_session)
    except web_session_service.AuthServiceUnavailable:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "AUTH_SERVICE_UNAVAILABLE",
                "message": "Authentication service is temporarily unavailable. Please try again shortly.",
            },
        )

    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "NOT_LOGGED_IN",
                "message": "Please log in to continue.",
            },
        )
    return email
