"""
Pydantic schemas for the Recruitment JD -> WhatsApp pipeline's job-description
domain. These are the ONLY shapes the JD extraction agent's output is allowed
to take once validated — nothing downstream (formatter, policy gate, Meta API)
ever sees raw/unvalidated LLM output (see jd_extraction_agent.py + JDValidationService).
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# Hard ceilings so a malicious/malformed JD (or a prompt-injected LLM response)
# can't blow up storage, WhatsApp message limits, or downstream rendering.
MAX_SHORT_FIELD_LEN = 200
MAX_TEXT_FIELD_LEN = 20000
MAX_LIST_ITEMS = 100
MAX_LIST_ITEM_LEN = 500


class ExperienceRange(BaseModel):
    min_years: Optional[float] = Field(default=None, ge=0, le=60)
    max_years: Optional[float] = Field(default=None, ge=0, le=60)

    @model_validator(mode="after")
    def _check_range(self) -> "ExperienceRange":
        if self.min_years is not None and self.max_years is not None:
            if self.min_years > self.max_years:
                raise ValueError(
                    f"experience.min_years ({self.min_years}) cannot exceed max_years ({self.max_years})"
                )
        return self


class SalaryRange(BaseModel):
    min: Optional[float] = Field(default=None, ge=0)
    max: Optional[float] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default=None, max_length=10)

    @model_validator(mode="after")
    def _check_range(self) -> "SalaryRange":
        if self.min is not None and self.max is not None:
            if self.min > self.max:
                raise ValueError(f"salary.min ({self.min}) cannot exceed salary.max ({self.max})")
        return self


class FieldConfidence(BaseModel):
    """
    Per-field confidence/uncertainty flags, so a recruiter (or the WhatsApp
    formatter) can tell "the JD genuinely didn't say" apart from "the model
    wasn't sure". Only populated for fields worth flagging; absence of a key
    means "extracted with normal confidence" — never fabricated.
    """
    uncertain_fields: List[str] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)
    notes: Optional[str] = Field(default=None, max_length=MAX_TEXT_FIELD_LEN)


def _bounded_str_list(v: List[str]) -> List[str]:
    if len(v) > MAX_LIST_ITEMS:
        raise ValueError(f"list has {len(v)} items, exceeds max of {MAX_LIST_ITEMS}")
    for item in v:
        if len(item) > MAX_LIST_ITEM_LEN:
            raise ValueError(f"list item exceeds max length of {MAX_LIST_ITEM_LEN} chars")
    return v


class ExtractedJD(BaseModel):
    """
    Strict structured output of the JD extraction agent, AFTER validation.
    Every field is optional except job_title — a JD extraction that couldn't
    even find a role name is not usable, and should be rejected upstream
    rather than stored as a near-empty record.

    `null`/None means "not present in the source JD" — the agent must never
    guess or invent a value. See jd_extraction_agent.py's system prompt.
    """

    job_title: str = Field(..., min_length=1, max_length=MAX_SHORT_FIELD_LEN)
    company: Optional[str] = Field(default=None, max_length=MAX_SHORT_FIELD_LEN)
    experience: Optional[ExperienceRange] = None
    skills: List[str] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)
    mandatory_skills: List[str] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)
    preferred_skills: List[str] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)
    location: List[str] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)
    salary: Optional[SalaryRange] = None
    employment_type: Optional[str] = Field(default=None, max_length=MAX_SHORT_FIELD_LEN)
    notice_period: Optional[str] = Field(default=None, max_length=MAX_SHORT_FIELD_LEN)
    job_description: Optional[str] = Field(default=None, max_length=MAX_TEXT_FIELD_LEN)
    requirements: List[str] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)
    confidence: Optional[FieldConfidence] = None

    _validate_skills = field_validator("skills", "mandatory_skills", "preferred_skills", "location", "requirements")(
        _bounded_str_list
    )

    @field_validator("job_title", "company", "employment_type", "notice_period")
    @classmethod
    def _no_control_chars(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        # Strip anything that isn't printable — defends against control-char
        # smuggling in a field that gets rendered straight into a WhatsApp message.
        cleaned = "".join(ch for ch in v if ch.isprintable() or ch in ("\n", "\t"))
        return cleaned.strip()


class OriginalEmail(BaseModel):
    """The untouched source, kept separately from the LLM's structured interpretation."""
    subject: str = Field(default="", max_length=MAX_SHORT_FIELD_LEN)
    sender: str = Field(default="", max_length=MAX_SHORT_FIELD_LEN)
    recipient: Optional[str] = Field(default=None, max_length=MAX_SHORT_FIELD_LEN)
    body: str = Field(default="", max_length=MAX_TEXT_FIELD_LEN)
    received_at: Optional[datetime] = None
    attachment_filenames: List[str] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)


class JobStatus(str, Enum):
    RECEIVED = "received"
    EXTRACTED = "extracted"
    VALIDATION_FAILED = "validation_failed"
    STORED = "stored"
    DUPLICATE = "duplicate"
    FAILED = "failed"


class WhatsAppSendStatus(str, Enum):
    NOT_SENT = "not_sent"
    DRY_RUN = "dry_run"
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    REJECTED_BY_POLICY = "rejected_by_policy"
    UNSUPPORTED = "unsupported"


class JDExtractionRequest(BaseModel):
    """Manual-test input for POST /api/jd/extract."""
    subject: str = Field(default="", max_length=MAX_SHORT_FIELD_LEN)
    body: str = Field(default="", max_length=MAX_TEXT_FIELD_LEN)
    attachment_text: str = Field(default="", max_length=MAX_TEXT_FIELD_LEN)


class JDValidateRequest(BaseModel):
    """Input for POST /api/jd/validate — validates an already-extracted JD dict."""
    extracted_jd: dict


class JobRecord(BaseModel):
    """
    Full persisted record for one processed email/JD (the `jobs` collection).
    Mirrors the structure suggested in the spec's section 4.
    """
    id: Optional[str] = Field(default=None, alias="_id")
    gmail_message_id: Optional[str] = None
    email_subject: str = ""
    sender: str = ""
    original_email: Optional[OriginalEmail] = None
    extracted_jd: Optional[ExtractedJD] = None
    normalized_jd: Optional[ExtractedJD] = None
    jd_hash: Optional[str] = None
    status: JobStatus = JobStatus.RECEIVED
    whatsapp_status: WhatsAppSendStatus = WhatsAppSendStatus.NOT_SENT
    is_duplicate_of: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"populate_by_name": True}


class GmailProcessingRecord(BaseModel):
    """Tracks which Gmail messages have already been processed (dedup at the source)."""
    gmail_message_id: str
    status: str = "processed"
    processed_at: datetime = Field(default_factory=datetime.utcnow)
    jd_id: Optional[str] = None
