"""
Tests for SearchPlan validation enforcement (POST /search/plan, POST /search/candidates)
and ValidationService coverage of resdex_schema.json enum fields.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from fastapi.testclient import TestClient
from app.main import app
from app.schemas.search_plan import SearchPlan
from app.services.validation_service import ValidationService

client = TestClient(app)


def _valid_plan_payload():
    return {
        "plan": {
            "keywords": {"required": ["Python"], "preferred": [], "excluded": []},
            "min_experience": 2,
            "max_experience": 5,
        },
        "submit_search": False,
    }


def test_direct_plan_valid_is_stored():
    res = client.post("/search/plan", json=_valid_plan_payload())
    assert res.status_code == 200, res.text
    assert res.json()["validation"]["valid"] is True


def test_direct_plan_invalid_enum_rejected():
    payload = _valid_plan_payload()
    payload["plan"]["gender"] = "Not A Real Option"
    res = client.post("/search/plan", json=payload)
    assert res.status_code == 422
    body = res.json()
    assert any("gender" in e for e in body["errors"])


def test_direct_plan_invalid_experience_range_rejected():
    payload = _valid_plan_payload()
    payload["plan"]["min_experience"] = 10
    payload["plan"]["max_experience"] = 2
    res = client.post("/search/plan", json=payload)
    assert res.status_code == 422
    body = res.json()
    assert any("min_experience" in e for e in body["errors"])


def test_direct_plan_invalid_ug_qualification_rejected():
    payload = _valid_plan_payload()
    payload["plan"]["ug_qualification"] = "Made Up Qualification"
    res = client.post("/search/plan", json=payload)
    assert res.status_code == 422
    body = res.json()
    assert any("ug_qualification" in e for e in body["errors"])


def test_candidates_endpoint_rejects_invalid_active_in_override():
    res = client.post(
        "/search/candidates",
        json={
            "requirement": "Python developer with 3 to 5 years experience in Bangalore",
            "active_in": "999 years",
        },
    )
    assert res.status_code == 422
    body = res.json()
    assert any("active_in" in e for e in body["errors"])


def test_validation_service_accepts_extensible_work_permit_value():
    """work_permit is `extensible: true` in resdex_schema.json — values outside
    the listed options must NOT be rejected (same treatment as company/location)."""
    service = ValidationService()
    plan = SearchPlan(work_permit=["Some Country Not In The List"])
    result = service.validate(plan)
    assert result.valid is True


def test_validation_service_rejects_invalid_designation_search_scope():
    service = ValidationService()
    plan = SearchPlan(designation_search_scope="Nonexistent Scope")
    result = service.validate(plan)
    assert result.valid is False
    assert any("designation_search_scope" in e for e in result.errors)
