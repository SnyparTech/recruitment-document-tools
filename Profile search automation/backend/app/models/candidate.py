from typing import List, Optional
from pydantic import BaseModel, Field
from app.models.requirement import ParsedRequirement, GeneratedQuery


class CandidateProfile(BaseModel):
    """Candidate profile domain model."""

    id: str = Field(..., description="Unique candidate identifier", examples=["candidate_001"])
    name: str = Field(..., description="Candidate full name", examples=["Aarav Sharma"])
    current_title: str = Field(
        ..., description="Current job title", examples=["Machine Learning Engineer"]
    )
    current_company: Optional[str] = Field(
        default=None, description="Current employer or organization", examples=["AI Labs"]
    )
    experience_years: float = Field(
        ..., ge=0.0, description="Years of relevant professional experience", examples=[2.4]
    )
    location: str = Field(..., description="Candidate city/location", examples=["Hyderabad"])
    skills: List[str] = Field(
        default_factory=list,
        description="Candidate technical and domain skills",
        examples=[["Python", "FastAPI", "Machine Learning", "NLP", "PyTorch"]],
    )
    education: Optional[str] = Field(
        default=None, description="Highest educational qualification", examples=["B.Tech"]
    )
    profile_url: str = Field(
        ..., description="Direct profile URL or reference link", examples=["https://www.naukri.com/profile/1"]
    )
    source: str = Field(default="naukri", description="Portal source", examples=["naukri"])
    match_score: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Calculated match score (0-100)"
    )
    matched_skills: List[str] = Field(
        default_factory=list, description="Skills present in both requirement and candidate"
    )
    missing_skills: List[str] = Field(
        default_factory=list, description="Required skills absent from candidate profile"
    )


class ProfileSearchResponse(BaseModel):
    """API response model for candidate search endpoint."""

    requirement: str = Field(..., description="Original user recruitment requirement")
    parsed_requirement: ParsedRequirement = Field(
        ..., description="Structured parsed requirement"
    )
    search_query: GeneratedQuery = Field(
        ..., description="Generated search query and parameters"
    )
    portal: str = Field(default="naukri", description="Target job portal used")
    mode: str = Field(default="mock", description="Execution mode ('mock' or 'live_selenium')")
    total_candidates_found: int = Field(
        ..., description="Total candidates found across portal before ranking"
    )
    returned_candidates: int = Field(
        ..., description="Number of top candidates returned (up to 10)"
    )
    top_candidates: List[CandidateProfile] = Field(
        ..., description="List of top matching candidate profiles ranked by score"
    )
