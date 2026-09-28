"""Schemas for the WhatsApp formatting + policy-gate + send pipeline stages."""
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.jd import MAX_TEXT_FIELD_LEN


class WhatsAppMessageTemplate(BaseModel):
    """
    Configurable template for turning a validated JD into a WhatsApp message
    (see whatsapp_formatter.py). Recruiters can change wording/emoji/section
    order later by editing this config — the formatter never lets the LLM (or
    any other free-text source) generate the WhatsApp message body directly.
    """
    header_emoji: str = "🚨"
    header_text: str = "JOB OPENING"
    role_label: str = "💼 Role"
    location_label: str = "📍 Location"
    experience_label: str = "💻 Experience"
    skills_label: str = "🛠 Required Skills"
    joining_label: str = "⏳ Joining"
    company_label: str = "🏢 Company"
    footer_text: str = "📩 Interested candidates can share their resume."
    bullet_char: str = "•"
    max_skills_shown: int = Field(default=12, ge=1, le=50)


class WhatsAppPreviewRequest(BaseModel):
    """Input for POST /api/whatsapp/preview — format a JD without sending."""
    job_id: Optional[str] = None
    extracted_jd: Optional[dict] = None


class WhatsAppPreviewResponse(BaseModel):
    message: str = Field(..., max_length=MAX_TEXT_FIELD_LEN)
    char_count: int


class WhatsAppCheckRequest(BaseModel):
    """Input for POST /api/whatsapp/check — run the policy/spam gate only."""
    job_id: str


class PolicyCheckResult(BaseModel):
    allowed: bool
    reason: Optional[str] = None
    checks_run: list[str] = Field(default_factory=list)


class WhatsAppSendRequest(BaseModel):
    """Input for POST /api/whatsapp/send — send an approved, already-checked message."""
    job_id: str
    force: bool = False  # explicit override is still subject to PolicyService; does not bypass it
