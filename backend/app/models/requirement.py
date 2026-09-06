from typing import List, Optional
from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Input payload containing a natural language recruitment requirement."""

    requirement: str = Field(
        ...,
        min_length=3,
        description="Natural language recruitment requirement description",
        examples=[
            "Find AI/ML Engineers in Hyderabad with 1-3 years experience and skills Python, FastAPI, Machine Learning and NLP"
        ],
    )
    portal: str = Field(
        default="naukri",
        description="Job portal to search candidates from (default: naukri)",
        examples=["naukri"],
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=10,
        description="Maximum number of top matching candidates to return (max 10)",
        examples=[10],
    )
    use_mock: bool = Field(
        default=False,
        description="Whether to use mock candidate data layer instead of live Selenium execution (default: false)",
        examples=[False],
    )


class ExperienceRange(BaseModel):
    """Structured experience range bounds."""

    min_years: Optional[float] = Field(
        default=None,
        description="Minimum years of professional experience",
        examples=[1.0],
    )
    max_years: Optional[float] = Field(
        default=None,
        description="Maximum years of professional experience",
        examples=[3.0],
    )


class ParsedRequirement(BaseModel):
    """Structured representation of the parsed recruitment requirement."""

    role: Optional[str] = Field(
        default=None,
        description="Target job title or role extracted from requirement",
        examples=["AI/ML Engineer"],
    )
    required_skills: List[str] = Field(
        default_factory=list,
        description="Mandatory skills and technologies extracted from requirement",
        examples=[["Python", "FastAPI", "Machine Learning", "NLP"]],
    )
    preferred_skills: List[str] = Field(
        default_factory=list,
        description="Optional or preferred skills extracted from requirement",
        examples=[[]],
    )
    experience: Optional[ExperienceRange] = Field(
        default=None,
        description="Experience range constraints",
    )
    location: Optional[str] = Field(
        default=None,
        description="Target candidate location or city",
        examples=["Hyderabad"],
    )
    education: Optional[str] = Field(
        default=None,
        description="Required educational degree qualification if specified",
        examples=[None],
    )


class GeneratedQuery(BaseModel):
    """Generated candidate-search query and parameters."""

    primary_query: str = Field(
        ...,
        description="Synthesized candidate search query string",
        examples=["AI ML Engineer Python FastAPI Machine Learning NLP"],
    )
    role_keywords: List[str] = Field(
        default_factory=list,
        description="Expanded role keyword variations for search querying",
        examples=[["AI Engineer", "ML Engineer", "Machine Learning Engineer"]],
    )
    skill_keywords: List[str] = Field(
        default_factory=list,
        description="Target skill keywords for search filtering",
        examples=[["Python", "FastAPI", "Machine Learning", "NLP"]],
    )
    location: Optional[str] = Field(
        default=None,
        description="Normalized location string for portal filtering",
        examples=["Hyderabad"],
    )
    min_experience: Optional[float] = Field(
        default=None,
        description="Minimum experience filter in years",
        examples=[1.0],
    )
    max_experience: Optional[float] = Field(
        default=None,
        description="Maximum experience filter in years",
        examples=[3.0],
    )
