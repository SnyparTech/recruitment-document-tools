from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator
from app.schemas.search_plan import SearchPlan


class CandidateSearchRequest(BaseModel):
    """API Request schema for candidate search."""

    requirement: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="Natural language recruitment requirement prompt (sanitized, max 2000 characters)",
        examples=[
            "Find AI/ML engineers in Hyderabad with 2 to 5 years of experience. Python, FastAPI, Machine Learning and NLP are mandatory. Salary should be 8 to 15 LPA. Prefer candidates who can join within 15 days."
        ],
    )
    execute: bool = Field(
        default=False,
        description="Whether to execute Selenium form filling (default: false for dry-run plan generation)",
    )
    submit_search: bool = Field(
        default=False,
        description="Whether to submit the search after filling form fields (default: false for safe inspection)",
    )

    @field_validator("requirement")
    @classmethod
    def sanitize_requirement(cls, val: str) -> str:
        """Sanitizes user input by stripping null bytes and dangerous control characters."""
        if not val or not val.strip():
            raise ValueError("Requirement prompt cannot be empty or pure whitespace.")
        # Strip null bytes and control chars (except standard newlines/tabs)
        cleaned = "".join(ch for ch in val if ch in "\n\r\t" or (32 <= ord(ch) <= 126) or ord(ch) > 127)
        cleaned = cleaned.strip()
        if len(cleaned) < 3:
            raise ValueError("Requirement prompt must contain at least 3 valid characters.")
        return cleaned


class ValidationResult(BaseModel):
    """Validation report against resdex_schema.json."""

    valid: bool = Field(default=True, description="Whether SearchPlan strictly conforms to Resdex schema")
    errors: List[str] = Field(default_factory=list, description="Validation error messages")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings or notices")


class ExecutionResult(BaseModel):
    """Selenium execution status report."""

    requested: bool = Field(default=False, description="Whether execution was requested")
    executed: bool = Field(default=False, description="Whether Selenium executed actions")
    form_filled: bool = Field(default=False, description="Whether Resdex form fields were filled")
    search_submitted: bool = Field(default=False, description="Whether Search button was clicked")
    fields_interacted: List[str] = Field(default_factory=list, description="Fields filled in the Resdex form")
    message: str = Field(default="", description="Summary message of execution status")


class CandidateSearchResponse(BaseModel):
    """Complete API response for candidate search."""

    requirement: str = Field(..., description="Original natural-language requirement prompt")
    search_plan: SearchPlan = Field(..., description="Structured, validated Resdex SearchPlan")
    validation: ValidationResult = Field(..., description="Schema validation report")
    execution: ExecutionResult = Field(..., description="Execution status report")
