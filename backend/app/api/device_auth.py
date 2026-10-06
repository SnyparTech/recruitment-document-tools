import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services import device_auth_service, otp_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Device Authorization"])


class RequestOtpRequest(BaseModel):
    email: str = Field(..., min_length=1)
    device_id: str = Field(..., min_length=1)


@router.post("/request-device-otp")
async def request_device_otp(payload: RequestOtpRequest):
    try:
        email = device_auth_service.normalize_and_validate_email(settings, payload.email)
        otp_service.send_otp(settings, email, payload.device_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return {"status": "otp_sent", "email": email}


class RegisterDeviceRequest(BaseModel):
    email: str = Field(..., min_length=1)
    device_id: str = Field(..., min_length=1)
    otp: str = Field(..., min_length=1)


@router.post("/register-device")
async def register_device(payload: RegisterDeviceRequest):
    try:
        email = device_auth_service.normalize_and_validate_email(settings, payload.email)
        otp_service.verify_otp(email, payload.device_id, payload.otp)
        device_auth_service.register_device(settings, email, payload.device_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return {"status": "registered", "device_id": payload.device_id}
