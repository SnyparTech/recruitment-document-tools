from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.candidate import CandidateProfile

client = TestClient(app)


def test_get_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "Candidate" in data["name"]
    assert data["status"] == "running"


def test_get_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_post_profiles_search_mock_success():
    payload = {
        "requirement": "Find AI/ML Engineers in Hyderabad with 1-3 years experience and skills Python, FastAPI, Machine Learning and NLP",
        "portal": "naukri",
        "limit": 10,
        "use_mock": True,
    }
    response = client.post("/profiles/search", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["portal"] == "naukri"
    assert data["mode"] == "mock"
    assert data["total_candidates_found"] >= 20
    assert data["returned_candidates"] == 10
    assert len(data["top_candidates"]) == 10

    # Verify structured parsed requirement
    parsed = data["parsed_requirement"]
    assert parsed["role"] == "AI/ML Engineer"
    assert "Python" in parsed["required_skills"]
    assert "FastAPI" in parsed["required_skills"]
    assert "Machine Learning" in parsed["required_skills"]
    assert "NLP" in parsed["required_skills"]
    assert parsed["location"] == "Hyderabad"
    assert parsed["experience"]["min_years"] == 1.0
    assert parsed["experience"]["max_years"] == 3.0

    # Verify generated search query
    query = data["search_query"]
    assert "AI ML Engineer" in query["primary_query"]
    assert "Python" in query["primary_query"]
    assert len(query["role_keywords"]) > 0

    # Verify top candidate fields & score
    top_cand = data["top_candidates"][0]
    assert "id" in top_cand
    assert "name" in top_cand
    assert "current_title" in top_cand
    assert "experience_years" in top_cand
    assert "location" in top_cand
    assert "skills" in top_cand
    assert "match_score" in top_cand
    assert "matched_skills" in top_cand
    assert "missing_skills" in top_cand
    assert "profile_url" in top_cand
    assert "source" in top_cand

    # Match score should be highest for top candidate
    assert top_cand["match_score"] >= 90.0


def test_post_profiles_search_custom_limit():
    payload = {
        "requirement": "Python developer in Hyderabad",
        "limit": 5,
        "use_mock": True,
    }
    response = client.post("/profiles/search", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["returned_candidates"] == 5
    assert len(data["top_candidates"]) == 5


def test_post_profiles_search_live_mode_delegation():
    """Verify live mode delegates to scraper when use_mock=False."""
    mock_candidates = [
        CandidateProfile(
            id="live_001",
            name="Live Candidate",
            current_title="AI/ML Engineer",
            experience_years=2.0,
            location="Hyderabad",
            skills=["Python", "FastAPI", "Machine Learning", "NLP"],
            profile_url="https://naukri.com/profile/live1",
        )
    ]
    with patch("app.portals.naukri.scraper.NaukriScraper.search", return_value=mock_candidates):
        payload = {
            "requirement": "AI/ML Engineer with Python in Hyderabad",
            "use_mock": False,
        }
        response = client.post("/profiles/search", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "live_selenium"
        assert len(data["top_candidates"]) == 1
        assert data["top_candidates"][0]["name"] == "Live Candidate"


def test_post_profiles_search_validation_errors():
    # Requirement too short
    res1 = client.post("/profiles/search", json={"requirement": "a"})
    assert res1.status_code == 422

    # Limit > 10
    res2 = client.post(
        "/profiles/search",
        json={"requirement": "Python dev", "limit": 20},
    )
    assert res2.status_code == 422


def test_post_profiles_search_unsupported_portal():
    payload = {
        "requirement": "Python developer in Hyderabad",
        "portal": "unknown_portal",
        "use_mock": True,
    }
    response = client.post("/profiles/search", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "PORTAL_NOT_SUPPORTED"
