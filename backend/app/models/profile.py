from typing import List, Optional
from pydantic import BaseModel, Field
from app.models.requirement import ParsedRequirement


class CandidateProfile(BaseModel):
    """Candidate profile model representing extracted and scored candidate data."""

    name: str = Field(..., description="Candidate full name")
    current_title: str = Field(..., description="Candidate current job title")
    experience: str = Field(..., description="Years of professional experience")
    location: str = Field(..., description="Candidate current city or location")
    skills: List[str] = Field(default_factory=list, description="List of technical and soft skills")
    education: Optional[str] = Field(default=None, description="Highest educational qualification")
    current_company: Optional[str] = Field(default=None, description="Current or most recent employer")
    profile_url: str = Field(..., description="Direct link or portal profile URL")
    match_score: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Calculated suitability score normalized from 0 to 100",
    )
    matched_skills: List[str] = Field(
        default_factory=list,
        description="Skills present in both the requirement and candidate profile",
    )
    missing_skills: List[str] = Field(
        default_factory=list,
        description="Required skills not found in candidate profile",
    )


class ProfileSearchResponse(BaseModel):
    """API response model for profile search endpoint."""

    requirement: str = Field(..., description="Original input requirement text")
    parsed_requirement: ParsedRequirement = Field(
        ..., description="Structured representation of parsed requirement"
    )
    total_profiles_found: int = Field(
        ..., description="Total number of candidates retrieved before ranking"
    )
    top_profiles: List[CandidateProfile] = Field(
        ..., description="Top matching candidate profiles ranked by score"
    )
