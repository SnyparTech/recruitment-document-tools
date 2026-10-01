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


def test_split_combined_locations():
    from app.agents.requirement_agent import RequirementAgent

    assert RequirementAgent._split_combined_locations("Bengaluru or Hyderabad") == ["Bengaluru", "Hyderabad"]
    assert RequirementAgent._split_combined_locations("Pune, Mumbai, Chennai") == ["Pune", "Mumbai", "Chennai"]
    assert RequirementAgent._split_combined_locations("New Delhi") == ["New Delhi"]
    assert RequirementAgent._split_combined_locations("Bengaluru/Hyderabad") == ["Bengaluru", "Hyderabad"]


def test_sanitize_llm_output_splits_combined_location_string():
    from app.agents.requirement_agent import RequirementAgent

    agent = RequirementAgent()
    sanitized = agent._sanitize_llm_output({"current_location": "Pune or Mumbai"})
    assert sanitized["current_location"] == ["Pune", "Mumbai"]


def test_chat_completion_with_retry_treats_null_content_as_failure_not_a_crash(monkeypatch):
    """Reasoning models can return HTTP 200 with content=None if their internal
    reasoning trace exhausts max_tokens before writing a real answer — this
    must be treated as a failed attempt, not raise on a bare .strip() call."""
    import httpx
    from app.agents.requirement_agent import _chat_completion_with_retry

    class FakeResponse:
        status_code = 200
        text = ""
        def json(self):
            return {"choices": [{"message": {"content": None}}]}

    class FakeClient:
        def post(self, *args, **kwargs):
            return FakeResponse()

    result = _chat_completion_with_retry(FakeClient(), "http://fake", {}, {}, ["some-model"])
    assert result is None


def test_provider_chain_prioritizes_nvidia_then_openrouter_then_groq_then_gemini(monkeypatch):
    from app.agents.requirement_agent import RequirementAgent
    from app.core.config import settings

    monkeypatch.setattr(settings, "NVIDIA_NIM_KEY", "nvapi-test")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "gsk-test")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "gemini-test")

    agent = RequirementAgent()
    chain = agent._provider_chain()
    assert [c[0] for c in chain] == ["nvidia", "openrouter", "groq", "gemini"]
    assert chain[0][1] == settings.NVIDIA_API_URL
    assert chain[0][3] == settings.NVIDIA_MODEL
    assert chain[1][1] == settings.OPENROUTER_API_URL
    assert chain[1][3] == settings.OPENROUTER_MODEL


def test_provider_chain_skips_providers_without_a_key(monkeypatch):
    from app.agents.requirement_agent import RequirementAgent
    from app.core.config import settings

    monkeypatch.setattr(settings, "NVIDIA_NIM_KEY", None)
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", None)
    monkeypatch.setattr(settings, "GROQ_API_KEY", "gsk-test")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)

    agent = RequirementAgent()
    chain = agent._provider_chain()
    assert [c[0] for c in chain] == ["groq"]


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


def test_normalize_keywords_caps_total_count():
    """
    Real bug from a live trace: the LLM generated 20 required + 16 preferred
    (36 total) keywords for one JD. Resdex ANDs required keywords together,
    so 20 required terms makes a search nearly unsatisfiable — and the
    combined keyword string from 36 terms blows past Resdex's own limit.
    Caps required to 8, preferred to 12, keeping the first-listed (assumed
    most-important-first) entries.
    """
    from app.agents.requirement_agent import RequirementAgent
    from app.schemas.search_plan import KeywordsPlan

    agent = RequirementAgent()
    keywords = KeywordsPlan(
        required=[f"Skill{i}" for i in range(20)],
        preferred=[f"Pref{i}" for i in range(16)],
    )
    agent._normalize_keywords(keywords)

    assert len(keywords.required) == agent.MAX_REQUIRED_KEYWORDS == 8
    assert len(keywords.preferred) == agent.MAX_PREFERRED_KEYWORDS == 12
    assert keywords.required == [f"Skill{i}" for i in range(8)]
    assert keywords.preferred == [f"Pref{i}" for i in range(12)]
