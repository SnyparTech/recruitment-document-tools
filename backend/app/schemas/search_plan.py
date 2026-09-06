from typing import List, Optional
from pydantic import BaseModel, Field


class KeywordsPlan(BaseModel):
    """Keywords and skills criteria for candidate search."""

    required: List[str] = Field(
        default_factory=list,
        description="Mandatory skills and technical keywords that must appear in candidate profile",
    )
    preferred: List[str] = Field(
        default_factory=list,
        description="Optional or nice-to-have skills",
    )
    excluded: List[str] = Field(
        default_factory=list,
        description="Keywords to explicitly exclude from search",
    )
    mandatory: bool = Field(
        default=True,
        description="Whether to mark all keywords as mandatory in Resdex",
    )
    search_scope: str = Field(
        default="Entire resume",
        description="Scope of keyword search: 'Entire resume', 'Resume title', 'Key skills', 'Resume title and Key skills'",
    )


class SalaryPlan(BaseModel):
    """Annual salary bounds and currency."""

    currency: str = Field(default="INR", description="Currency code (e.g. INR, USD)")
    min: Optional[float] = Field(default=None, description="Minimum annual salary in lakhs/units")
    max: Optional[float] = Field(default=None, description="Maximum annual salary in lakhs/units")
    include_unspecified: Optional[bool] = Field(
        default=None,
        description="Include candidates without current salary specified",
    )


class AgeRangePlan(BaseModel):
    """Candidate age range bounds."""

    min: Optional[int] = Field(default=None, ge=18, le=65, description="Minimum candidate age")
    max: Optional[int] = Field(default=None, ge=18, le=65, description="Maximum candidate age")


class SearchPlan(BaseModel):
    """
    Structured, schema-driven representation of a Resdex candidate search.
    Only fields explicitly requested by the recruiter are populated; unmentioned fields remain None.
    """

    keywords: Optional[KeywordsPlan] = Field(
        default=None,
        description="Keywords and skills criteria",
    )
    min_experience: Optional[float] = Field(
        default=None,
        ge=0,
        le=50,
        description="Minimum years of professional experience",
    )
    max_experience: Optional[float] = Field(
        default=None,
        ge=0,
        le=50,
        description="Maximum years of professional experience",
    )
    current_location: Optional[List[str]] = Field(
        default=None,
        description="List of target city locations",
    )
    include_relocation: Optional[bool] = Field(
        default=None,
        description="Include candidates who prefer to relocate",
    )
    exclude_anywhere_location: Optional[bool] = Field(
        default=None,
        description="Exclude candidates who mentioned anywhere",
    )
    salary: Optional[SalaryPlan] = Field(
        default=None,
        description="Annual salary constraints",
    )

    # Employment Details
    department_role: Optional[List[str]] = Field(
        default=None,
        description="Department and role categories",
    )
    industry: Optional[List[str]] = Field(
        default=None,
        description="Target candidate industries",
    )
    company: Optional[List[str]] = Field(
        default=None,
        description="Target companies",
    )
    company_search_scope: Optional[str] = Field(
        default="Current company",
        description="Scope for company search",
    )
    exclude_company: Optional[List[str]] = Field(
        default=None,
        description="Companies to exclude",
    )
    exclude_company_search_scope: Optional[str] = Field(
        default="Current company",
        description="Scope for excluded company search",
    )
    designation: Optional[List[str]] = Field(
        default=None,
        description="Job titles/designations",
    )
    designation_search_scope: Optional[str] = Field(
        default="Current designation",
        description="Scope for designation search",
    )

    # Notice Period
    notice_period: Optional[List[str]] = Field(
        default=None,
        description="Target notice period options (e.g. '0-15 days', '1 month')",
    )

    # Diversity Hiring
    gender: Optional[str] = Field(
        default=None,
        description="Gender criteria if explicitly requested ('All candidates', 'Male candidates', 'Female candidates')",
    )
    career_break: Optional[str] = Field(
        default=None,
        description="Career break option ('Women returning to work')",
    )
    differently_abled: Optional[str] = Field(
        default=None,
        description="Differently-abled category",
    )
    defence_background: Optional[str] = Field(
        default=None,
        description="Defence background category",
    )

    # Additional Details
    candidate_category: Optional[str] = Field(
        default=None,
        description="Candidate social category if explicitly requested",
    )
    candidate_age: Optional[AgeRangePlan] = Field(
        default=None,
        description="Candidate age range",
    )
    job_type: Optional[str] = Field(
        default=None,
        description="Job type ('Any', 'Permanent', 'Temporary/Contract job')",
    )
    employment_type: Optional[str] = Field(
        default=None,
        description="Employment type ('Any', 'Full time', 'Part time')",
    )
    work_permit: Optional[List[str]] = Field(
        default=None,
        description="Work permit countries",
    )

    # Display Details & Search Period
    candidate_display: Optional[str] = Field(
        default="All candidates",
        description="Candidate display option ('All candidates', 'Modified candidates')",
    )
    verified_mobile: Optional[bool] = Field(
        default=None,
        description="Require verified mobile number",
    )
    verified_email: Optional[bool] = Field(
        default=None,
        description="Require verified email ID",
    )
    attached_resume: Optional[bool] = Field(
        default=None,
        description="Require attached resume",
    )
    active_in: Optional[str] = Field(
        default="6 months",
        description="Search active period (e.g. '30 days', '6 months')",
    )

    # Confidence and Uncertainty Tracking
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Agent confidence score in generating the search plan",
    )
    uncertain_fields: List[str] = Field(
        default_factory=list,
        description="List of fields where requirement was ambiguous",
    )
