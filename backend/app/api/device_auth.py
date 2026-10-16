"""
Website login (email+OTP -> HttpOnly session cookie, sliding 30-day expiry)
and the pairing handoff that lets the Chrome extension inherit that login
without its own standalone auth flow. See core/web_auth.py (website) and
core/device_auth.py (extension) for the dependencies these endpoints feed.
"""
import logging

from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.web_auth import SESSION_COOKIE_NAME, verify_website_session
from app.services import device_auth_service, device_token_service, otp_service, pairing_service, web_session_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Sentinel device_id for login-context OTPs — otp_service's _pending store is
# keyed by (email, device_id) and this flow has no real device yet.
_WEB_LOGIN_SENTINEL = "__web_login__"

SESSION_TTL_SECONDS = web_session_service.SESSION_TTL_SECONDS


class RequestLoginOtpRequest(BaseModel):
    email: str = Field(..., min_length=1)


@router.post("/login/request-otp")
async def request_login_otp(payload: RequestLoginOtpRequest):
    try:
        email = device_auth_service.normalize_and_validate_email(settings, payload.email)
        await otp_service.send_otp(settings, email, _WEB_LOGIN_SENTINEL)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return {"status": "otp_sent", "email": email}


class VerifyLoginOtpRequest(BaseModel):
    email: str = Field(..., min_length=1)
    otp: str = Field(..., min_length=1)


@router.post("/login/verify")
async def verify_login_otp(payload: VerifyLoginOtpRequest, response: Response):
    try:
        email = device_auth_service.normalize_and_validate_email(settings, payload.email)
        otp_service.verify_otp(email, _WEB_LOGIN_SENTINEL, payload.otp)
        token = web_session_service.create_session(email)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except web_session_service.AuthServiceUnavailable:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is temporarily unavailable. Please try again shortly.",
        )

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
    )
    return {"status": "logged_in", "email": email}


@router.get("/me")
async def get_me(web_session: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME)):
    """Status check, not a gate — 'not logged in' is a normal result here,
    not an error (unlike verify_website_session, which protected endpoints
    use to actually deny access). Lets the frontend decide whether to show
    the login page at all (auth_enabled) before asking who's logged in."""
    auth_enabled = bool(getattr(settings, "AUTH_ENABLED", False))
    if not auth_enabled:
        return {"status": "success", "auth_enabled": False, "email": None}

    try:
        email = web_session_service.get_session_email(web_session)
    except web_session_service.AuthServiceUnavailable:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is temporarily unavailable. Please try again shortly.",
        )
    return {"status": "success", "auth_enabled": True, "email": email}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    return {"status": "logged_out"}


@router.post("/pairing-code")
async def create_pairing_code(email: str = Depends(verify_website_session)):
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Log in first to pair a device.")
    try:
        code = pairing_service.create_pairing_code(email)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    return {"status": "success", "code": code, "expires_in_seconds": pairing_service.CODE_TTL_SECONDS}


class PairDeviceRequest(BaseModel):
    code: str = Field(..., min_length=1)
    device_id: str = Field(..., min_length=1)


@router.post("/pair-device")
async def pair_device(payload: PairDeviceRequest):
    try:
        email = pairing_service.consume_pairing_code(payload.code)
        device_token = device_token_service.issue_device_token(payload.device_id, email)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return {"status": "paired", "device_id": payload.device_id, "device_token": device_token}
