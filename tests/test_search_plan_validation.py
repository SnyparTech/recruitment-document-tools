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


def test_validation_service_rejects_keyword_over_200_chars():
    service = ValidationService()
    plan = SearchPlan(keywords={"required": ["A" * 201]})
    result = service.validate(plan)
    assert result.valid is False
    assert any("200-character limit" in e for e in result.errors)


def test_validation_service_accepts_keyword_at_exactly_200_chars():
    service = ValidationService()
    plan = SearchPlan(keywords={"required": ["A" * 200]})
    result = service.validate(plan)
    assert result.valid is True


def test_validation_service_rejects_duplicate_keyword_case_insensitive_across_lists():
    service = ValidationService()
    plan = SearchPlan(keywords={"required": ["Python"], "preferred": ["python"]})
    result = service.validate(plan)
    assert result.valid is False
    assert any("Duplicate keyword" in e for e in result.errors)


def test_validation_service_rejects_filler_keyword():
    service = ValidationService()
    plan = SearchPlan(keywords={"required": ["Python", "or", "certified", "similar"]})
    result = service.validate(plan)
    assert result.valid is False
    assert sum("filler/connector word" in e for e in result.errors) == 3


def test_validation_service_accepts_legit_term_containing_filler_substring():
    service = ValidationService()
    plan = SearchPlan(keywords={"required": ["AWS Certified Solutions Architect"]})
    result = service.validate(plan)
    assert result.valid is True


def test_requirement_agent_normalize_keywords_drops_filler_words_but_keeps_real_credentials():
    from app.agents.requirement_agent import RequirementAgent
    from app.schemas.search_plan import KeywordsPlan

    agent = RequirementAgent()
    keywords = KeywordsPlan(
        required=["Python", "or", "similar", "certified", "AWS Certified Solutions Architect", "experience", "Hands-on"],
        preferred=["Varonis", "such as", "Django"],
        excluded=[],
    )
    agent._normalize_keywords(keywords)

    assert keywords.required == ["Python", "AWS Certified Solutions Architect"]
    assert keywords.preferred == ["Varonis", "Django"]


def test_active_in_defaults_to_15_days_when_not_mentioned():
    from app.agents.requirement_agent import RequirementAgent

    agent = RequirementAgent()
    plan = agent.generate_search_plan("Python developer in Bengaluru with 3-5 years experience")
    assert plan.active_in == "15 days"


def test_active_in_corrects_hallucinated_value_with_no_textual_basis():
    from app.agents.requirement_agent import RequirementAgent
    from app.schemas.search_plan import SearchPlan

    agent = RequirementAgent()
    # Simulates an LLM returning a non-null guess despite no mention in the text.
    fake_llm_plan = SearchPlan(active_in="6 months")
    corrected = agent._post_process_plan(fake_llm_plan, "Python developer in Bengaluru with 3-5 years experience")
    assert corrected.active_in == "15 days"


def test_active_in_respects_explicit_mention_and_normalizes_to_valid_enum():
    from app.agents.requirement_agent import RequirementAgent
    from app.schemas.search_plan import SearchPlan

    agent = RequirementAgent()
    # LLM echoes the JD's own phrasing instead of the exact Resdex enum value.
    fake_llm_plan = SearchPlan(active_in="last 30 days")
    corrected = agent._post_process_plan(fake_llm_plan, "Only show candidates active in the last 30 days.")
    assert corrected.active_in == "30 days"


def test_requirement_agent_normalize_keywords_dedupes_and_drops_overlong():
    from app.agents.requirement_agent import RequirementAgent
    from app.schemas.search_plan import KeywordsPlan

    agent = RequirementAgent()
    keywords = KeywordsPlan(
        required=["Python", "python", "PYTHON", "Django"],
        preferred=["Python", "FastAPI", "A" * 250],
        excluded=[],
    )
    agent._normalize_keywords(keywords)

    assert keywords.required == ["Python", "Django"]
    assert keywords.preferred == ["FastAPI"]  # "Python" dropped: already in required; 250-char entry dropped
    assert all(len(k) <= agent.MAX_KEYWORD_LENGTH for k in keywords.required + keywords.preferred)
