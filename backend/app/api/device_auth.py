import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services import device_auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Device Authorization"])


class RegisterDeviceRequest(BaseModel):
    email: str = Field(..., min_length=1)
    device_id: str = Field(..., min_length=1)


@router.post("/register-device")
async def register_device(payload: RegisterDeviceRequest):
    try:
        device_auth_service.register_device(settings, payload.email, payload.device_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return {"status": "registered", "device_id": payload.device_id}
