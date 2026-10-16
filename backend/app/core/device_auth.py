"""
FastAPI dependency enforcing the extension's device-lock. Apply via
`dependencies=[Depends(verify_device)]` — currently applied to the 3
extension-only endpoints on the search_device_router (see api/search.py).

A device gets here only via a real website login: the recruiter logs in on
the website (see api/device_auth.py's /auth/login/* routes), gets a
short-lived pairing code, and pastes it into the extension popup once
(POST /auth/pair-device) to receive this long-lived X-Device-Token. There is
no standalone email+OTP flow on the extension side anymore — see
services/device_token_service.py and services/pairing_service.py.
"""
from typing import Optional

from fastapi import Header, HTTPException, status

from app.core.config import settings
from app.services import device_token_service

DEVICE_ID_HEADER_NAME = "X-Device-Id"
DEVICE_TOKEN_HEADER_NAME = "X-Device-Token"


async def verify_device(
    x_device_id: Optional[str] = Header(default=None, alias=DEVICE_ID_HEADER_NAME),
    x_device_token: Optional[str] = Header(default=None, alias=DEVICE_TOKEN_HEADER_NAME),
) -> Optional[str]:
    if not getattr(settings, "AUTH_ENABLED", False):
        return x_device_id  # lock OFF — behave as before

    try:
        verified = device_token_service.verify_device_token(x_device_id, x_device_token)
    except device_token_service.AuthServiceUnavailable:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "AUTH_SERVICE_UNAVAILABLE",
                "message": "Authentication service is temporarily unavailable. Please try again shortly.",
            },
        )

    if not verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "DEVICE_NOT_AUTHORIZED",
                "message": "This device is not paired. Log into the website and pair it from the extension popup.",
            },
        )
    return x_device_id
