import pytest
from app.models.candidate import CandidateProfile
from app.models.requirement import ExperienceRange, ParsedRequirement
from app.services.matching_service import MatchingService


def test_matching_skills_calculation():
    matcher = MatchingService()
    req = ParsedRequirement(
        role="AI/ML Engineer",
        required_skills=["Python", "FastAPI", "Machine Learning", "NLP"],
        experience=ExperienceRange(min_years=1.0, max_years=3.0),
        location="Hyderabad",
    )

    # Candidate with 3 matching skills, 1 missing
    candidate = CandidateProfile(
        id="c1",
        name="Candidate One",
        current_title="AI/ML Engineer",
        experience_years=2.0,
        location="Hyderabad",
        skills=["Python", "FastAPI", "Machine Learning", "Docker"],
        education="B.Tech",
        profile_url="https://naukri.com/profile/c1",
    )

    scored = matcher.score_candidate(candidate, req)

    assert "Python" in scored.matched_skills
    assert "FastAPI" in scored.matched_skills
    assert "Machine Learning" in scored.matched_skills
    assert "NLP" in scored.missing_skills
    assert scored.match_score > 70.0


def test_matching_role_similarity():
    matcher = MatchingService()
    req = ParsedRequirement(
        role="AI/ML Engineer",
        required_skills=["Python"],
        location="Hyderabad",
    )

    # High similarity role in same cluster
    c_ml = CandidateProfile(
        id="c_ml",
        name="ML Eng",
        current_title="Machine Learning Engineer",
        experience_years=2.0,
        location="Hyderabad",
        skills=["Python"],
        profile_url="https://naukri.com/profile/ml",
    )

    # Irrelevant role
    c_fe = CandidateProfile(
        id="c_fe",
        name="Frontend Eng",
        current_title="Frontend React Developer",
        experience_years=2.0,
        location="Hyderabad",
        skills=["Python"],
        profile_url="https://naukri.com/profile/fe",
    )

    score_ml = matcher.score_candidate(c_ml, req).match_score
    score_fe = matcher.score_candidate(c_fe, req).match_score

    assert score_ml > score_fe


def test_matching_location_synonyms():
    matcher = MatchingService()
    req = ParsedRequirement(
        role="Python Developer",
        required_skills=["Python"],
        location="Hyderabad",
    )

    c_hyd_tel = CandidateProfile(
        id="c_hyd",
        name="Hyd Candidate",
        current_title="Python Developer",
        experience_years=2.0,
        location="Hyderabad, Telangana",
        skills=["Python"],
        profile_url="https://naukri.com/profile/hyd",
    )

    scored = matcher.score_candidate(c_hyd_tel, req)
    # Full score on location
    assert scored.match_score == 100.0


def test_matching_weight_redistribution_without_education():
    matcher = MatchingService()

    # Requirement without education
    req_no_edu = ParsedRequirement(
        role="AI/ML Engineer",
        required_skills=["Python", "Machine Learning"],
        experience=ExperienceRange(min_years=1.0, max_years=3.0),
        location="Hyderabad",
        education=None,
    )

    perfect_cand = CandidateProfile(
        id="c_perfect",
        name="Perfect Match",
        current_title="AI/ML Engineer",
        experience_years=2.0,
        location="Hyderabad",
        skills=["Python", "Machine Learning"],
        education=None,
        profile_url="https://naukri.com/profile/perf",
    )

    scored = matcher.score_candidate(perfect_cand, req_no_edu)
    # Perfect candidate should achieve 100.0 due to weight redistribution
    assert scored.match_score == 100.0
