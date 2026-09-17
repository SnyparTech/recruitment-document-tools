from typing import List, Optional
from pydantic import BaseModel, Field


class CandidateResult(BaseModel):
    """
    A single candidate as scraped from the Naukri Resdex results page by the
    extension. Deliberately lenient — only `name` is required, since real-world
    DOM extraction will often be missing individual fields (Resdex may not
    render them, or the extractor's selectors may miss a particular card).
    Fields here are the raw scraped values; ranking/normalization is a
    separate, later step (see candidate_ranking_service.py) that must not
    fabricate values for fields that were never found.
    """

    name: str = Field(..., min_length=1, description="Candidate display name")
    title: Optional[str] = Field(default=None, description="Current/most recent job title")
    company: Optional[str] = Field(default=None, description="Current/most recent company")
    experience: Optional[str] = Field(
        default=None,
        description="Raw experience text as shown on Resdex (e.g. '5 yrs 3 months'), not yet parsed to a number",
    )
    location: Optional[str] = Field(default=None, description="Candidate location as shown on Resdex")
    skills: List[str] = Field(default_factory=list, description="Skills/keywords shown on the candidate card")
    education: Optional[str] = Field(default=None, description="Highest qualification, if shown on the card")
    notice_period: Optional[str] = Field(default=None, description="Notice period, if shown on the card")
    profile_url: Optional[str] = Field(default=None, description="Absolute URL to the candidate's full profile")
    resdex_candidate_id: Optional[str] = Field(
        default=None,
        description="Resdex's own candidate/profile identifier if it could be extracted (from a data-id "
        "attribute or the profile URL) — the strongest available dedup key after profile_url",
    )


class CandidateExtractionDiagnostics(BaseModel):
    """
    Self-reported diagnostics from the extension's DOM extractor for a single
    results-page scrape. Used to calibrate selectors against real Resdex
    markup (no captured HTML sample exists in this repo) without needing to
    persist or expose any candidate PII — this only describes DOM structure
    and per-field hit/miss counts, never candidate content.
    """

    containers_detected: int = Field(default=0, description="Number of distinct candidate card containers found")
    candidates_extracted: int = Field(default=0, description="Number of candidates successfully parsed from those containers")
    field_hit_counts: dict = Field(
        default_factory=dict,
        description="Per-field count of how many extracted candidates had that field populated, e.g. {'title': 8, 'location': 3}",
    )
    selector_strategy: Optional[str] = Field(
        default=None, description="Which container-detection strategy succeeded (for calibration)"
    )
    warnings: List[str] = Field(default_factory=list, description="Non-fatal extraction issues, e.g. cards found but no profile link")


class SubmitCandidateResultsRequest(BaseModel):
    candidates: List[CandidateResult] = Field(default_factory=list, max_length=50)
    page: int = Field(default=1, ge=1, description="Results page number this batch was scraped from")
    diagnostics: Optional[CandidateExtractionDiagnostics] = Field(default=None)


class RankedCandidate(CandidateResult):
    """
    A CandidateResult augmented with an explainable match score against the
    currently active SearchPlan. Deliberately separates:
      - match_score: 0-100, computed ONLY from requirement dimensions that were
        both (a) specified in the SearchPlan and (b) extractable for this
        candidate. Never fabricated for dimensions with no data.
      - data_completeness: 0-100, the fraction of SearchPlan-specified
        dimensions that had candidate data available to score at all — lets
        the recruiter tell "poor match" apart from "we don't actually know."
      - matched_requirements / missing_requirements: human-readable, per
        dimension, only for dimensions that WERE scored.
      - unavailable_info: dimensions the SearchPlan asked about but couldn't be
        scored because the extractor didn't get that field for this candidate.
    `scored=False` (with all the above at their defaults) means the SearchPlan
    had no scorable requirements at all (e.g. an empty plan) — not that the
    candidate is a 0% match.
    """

    scored: bool = Field(default=False, description="Whether any SearchPlan requirement could be scored at all")
    match_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    data_completeness: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    matched_requirements: List[str] = Field(default_factory=list)
    missing_requirements: List[str] = Field(default_factory=list)
    unavailable_info: List[str] = Field(default_factory=list)
