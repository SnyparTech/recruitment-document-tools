from fastapi.testclient import TestClient
import pytest
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_api_root_and_health(client):
    r_root = client.get("/")
    assert r_root.status_code == 200
    assert r_root.json()["status"] == "running"

    r_health = client.get("/health")
    assert r_health.status_code == 200
    assert r_health.json()["status"] == "healthy"


def test_api_search_candidates_dry_run(client):
    req_body = {
        "requirement": (
            "Find AI/ML engineers in Hyderabad with 2 to 5 years of experience. "
            "Python, FastAPI, Machine Learning and NLP are mandatory. "
            "Salary should be 8 to 15 LPA. Prefer candidates who can join within 15 days."
        ),
        "execute": False,
        "submit_search": False,
    }

    response = client.post("/search/candidates", json=req_body)
    assert response.status_code == 200
    data = response.json()

    # Verify Response Structure
    assert "requirement" in data
    assert "search_plan" in data
    assert "validation" in data
    assert "execution" in data

    # Verify SearchPlan Content
    plan = data["search_plan"]
    assert "Python" in plan["keywords"]["required"]
    assert "FastAPI" in plan["keywords"]["required"]
    assert plan["min_experience"] == 2.0
    assert plan["max_experience"] == 5.0
    assert plan["current_location"] == ["Hyderabad"]
    assert plan["salary"]["min"] == 8.0
    assert plan["salary"]["max"] == 15.0
    assert plan["notice_period"] == ["0-15 days"]

    # Verify Validation
    assert data["validation"]["valid"] is True
    assert len(data["validation"]["errors"]) == 0

    # Verify Execution Status (Dry-run)
    assert data["execution"]["requested"] is False
    assert data["execution"]["executed"] is False
    assert data["execution"]["form_filled"] is False
    assert "Dry-run mode" in data["execution"]["message"]


def test_api_search_candidates_validation_rejection(client):
    # Prompt with impossible experience constraints (e.g. min 10 max 2) handled gracefully
    req_body = {
        "requirement": "Python developer in Hyderabad",
        "execute": False,
    }
    response = client.post("/search/candidates", json=req_body)
    assert response.status_code == 200
    data = response.json()
    assert data["validation"]["valid"] is True
