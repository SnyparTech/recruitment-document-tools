import pytest
from app.models.candidate import CandidateProfile
from app.models.requirement import ParsedRequirement
from app.services.ranking_service import RankingService


def test_ranking_descending_order_and_top_10_limit():
    ranking = RankingService()
    req = ParsedRequirement(
        role="AI/ML Engineer",
        required_skills=["Python", "FastAPI", "Machine Learning", "NLP"],
        location="Hyderabad",
    )

    # Generate 25 candidates with varying scores
    candidates = []
    for i in range(25):
        if i < 5:
            skills = ["Python", "FastAPI", "Machine Learning", "NLP"]
            loc = "Hyderabad"
        elif i < 15:
            skills = ["Python", "FastAPI"]
            loc = "Hyderabad"
        else:
            skills = ["Java", "Spring Boot"]
            loc = "Pune"

        candidates.append(
            CandidateProfile(
                id=f"c_{i}",
                name=f"Candidate {i}",
                current_title="AI/ML Engineer" if i < 10 else "Software Engineer",
                experience_years=float(i % 5 + 1),
                location=loc,
                skills=skills,
                profile_url=f"https://naukri.com/profile/{i}",
            )
        )

    top_candidates, total_found = ranking.rank_candidates(candidates, req, limit=10)

    assert total_found == 25
    assert len(top_candidates) == 10

    # Ensure strictly sorted descending
    scores = [c.match_score for c in top_candidates]
    assert scores == sorted(scores, reverse=True)


def test_ranking_pagination_offset():
    ranking = RankingService()
    req = ParsedRequirement(role="Python Developer", required_skills=["Python"])

    candidates = [
        CandidateProfile(
            id=f"c_{i}",
            name=f"Candidate {i}",
            current_title="Python Developer",
            experience_years=float(i + 1),
            location="Hyderabad",
            skills=["Python"],
            profile_url=f"https://naukri.com/profile/{i}",
        )
        for i in range(25)
    ]

    # Page 1: Top 10
    page_1, total = ranking.rank_candidates(candidates, req, limit=10, offset=0)
    assert len(page_1) == 10
    assert page_1[0].name == "Candidate 24"

    # Page 2: Next 10
    page_2, total = ranking.rank_candidates(candidates, req, limit=10, offset=10)
    assert len(page_2) == 10
    assert page_2[0].name == "Candidate 14"

    # Ensure Page 1 and Page 2 do not overlap
    page_1_ids = {c.id for c in page_1}
    page_2_ids = {c.id for c in page_2}
    assert page_1_ids.isdisjoint(page_2_ids)


def test_ranking_custom_lower_limit():
    ranking = RankingService()
    req = ParsedRequirement(role="Python Developer", required_skills=["Python"])

    candidates = [
        CandidateProfile(
            id=f"c_{i}",
            name=f"Candidate {i}",
            current_title="Python Developer",
            experience_years=2.0,
            location="Hyderabad",
            skills=["Python"],
            profile_url=f"https://naukri.com/profile/{i}",
        )
        for i in range(15)
    ]

    top_candidates, total_found = ranking.rank_candidates(candidates, req, limit=5)
    assert total_found == 15
    assert len(top_candidates) == 5
