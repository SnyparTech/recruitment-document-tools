"""
FastAPI dependency enforcing the extension device-lock (see
services/device_auth_service.py). Apply via `dependencies=[Depends(verify_device)]`
on a router — currently applied to the search_router, since that's the only
router the extension itself calls.
"""
from typing import Optional

from fastapi import Header, HTTPException, status

from app.core.config import settings
from app.services import device_auth_service

DEVICE_ID_HEADER_NAME = "X-Device-Id"


async def verify_device(
    x_device_id: Optional[str] = Header(default=None, alias=DEVICE_ID_HEADER_NAME),
) -> Optional[str]:
    if not device_auth_service.device_lock_enabled(settings):
        return x_device_id  # lock OFF (no tokens configured) — behave as before

    if not x_device_id or not device_auth_service.is_authorized(x_device_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "DEVICE_NOT_AUTHORIZED",
                "message": "This device is not authorized. Register it with a one-time token via POST /auth/register-device.",
            },
        )
    return x_device_id
