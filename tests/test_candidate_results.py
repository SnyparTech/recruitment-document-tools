"""
Tests for candidate result storage: dedup logic (candidate_store_service) and
the POST/GET/DELETE /search/results endpoints.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from fastapi.testclient import TestClient
from app.main import app
from app.schemas.candidate_result import CandidateResult
from app.services.candidate_store_service import candidate_dedup_key, merge_candidates

client = TestClient(app)


def _clear():
    client.delete("/search/results")


def test_dedup_key_prefers_profile_url():
    c = CandidateResult(name="A", profile_url="https://x/1", resdex_candidate_id="99", company="Acme")
    assert candidate_dedup_key(c) == "url:https://x/1"


def test_dedup_key_falls_back_to_resdex_id_then_name_company_then_name():
    with_id = CandidateResult(name="A", resdex_candidate_id="99", company="Acme")
    assert candidate_dedup_key(with_id) == "id:99"

    with_company = CandidateResult(name="Jane Doe", company="Acme Corp")
    assert candidate_dedup_key(with_company) == "namecompany:janedoe:acmecorp"

    name_only = CandidateResult(name="Jane Doe")
    assert candidate_dedup_key(name_only) == "name:janedoe"


def test_merge_candidates_dedupes_and_prefers_newer_record_on_collision():
    existing = [CandidateResult(name="Jane Doe", company="Acme", title="Old Title")]
    new = [CandidateResult(name="Jane Doe", company="Acme", title="New Title")]
    merged = merge_candidates(existing, new)
    assert len(merged) == 1
    assert merged[0].title == "New Title"


def test_merge_candidates_keeps_distinct_same_name_different_company():
    existing = [CandidateResult(name="Jane Doe", company="Acme")]
    new = [CandidateResult(name="Jane Doe", company="Globex")]
    merged = merge_candidates(existing, new)
    assert len(merged) == 2


def test_post_results_endpoint_stores_and_get_returns_them():
    _clear()
    res = client.post("/search/results", json={
        "page": 1,
        "candidates": [
            {"name": "Jane Doe", "company": "Acme", "skills": ["Python"]},
            {"name": "John Smith"},
        ],
        "diagnostics": {
            "containers_detected": 5,
            "candidates_extracted": 2,
            "field_hit_counts": {"name": 2, "company": 1},
            "selector_strategy": "profile-link-anchor",
            "warnings": ["3 containers had no matching profile link"],
        },
    })
    assert res.status_code == 200, res.text
    assert res.json()["total_stored"] == 2

    res_get = client.get("/search/results")
    assert res_get.status_code == 200
    body = res_get.json()
    assert body["has_results"] is True
    assert body["count"] == 2
    names = {c["name"] for c in body["candidates"]}
    assert names == {"Jane Doe", "John Smith"}
    _clear()


def test_post_results_rejects_candidate_missing_name():
    _clear()
    res = client.post("/search/results", json={"page": 1, "candidates": [{"company": "Acme"}]})
    assert res.status_code == 422


def test_post_results_rejects_batch_over_50():
    _clear()
    candidates = [{"name": f"Person {i}"} for i in range(51)]
    res = client.post("/search/results", json={"page": 1, "candidates": candidates})
    assert res.status_code == 422


def test_post_results_empty_batch_does_not_error():
    _clear()
    res = client.post("/search/results", json={"page": 1, "candidates": []})
    assert res.status_code == 200
    assert res.json()["total_stored"] == 0


def test_delete_results_clears_state():
    client.post("/search/results", json={"page": 1, "candidates": [{"name": "Jane Doe"}]})
    client.delete("/search/results")
    res = client.get("/search/results")
    assert res.json()["has_results"] is False
    assert res.json()["count"] == 0
