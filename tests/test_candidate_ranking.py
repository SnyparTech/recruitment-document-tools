"""
Tests for candidate_ranking_service.py — explainable ranking against SearchPlan.
Focus: no fabricated scores, data_completeness distinguishes "poor match" from
"we don't know", and weighting only spans dimensions actually specified+available.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.schemas.candidate_result import CandidateResult
from app.schemas.search_plan import KeywordsPlan, SearchPlan
from app.services.candidate_ranking_service import (
    parse_experience_years,
    rank_candidate,
    rank_candidates,
)


def test_parse_experience_years_handles_years_and_months():
    assert parse_experience_years("6 yrs 2 months") == 6.17
    assert parse_experience_years("3 years") == 3.0
    assert parse_experience_years(None) is None
    assert parse_experience_years("Fresher") is None  # no confident parse -> unavailable, not 0


def test_empty_plan_yields_unscored_not_zero():
    plan = SearchPlan()  # nothing specified
    candidate = CandidateResult(name="Jane Doe", skills=["Python"])
    ranked = rank_candidate(candidate, plan)
    assert ranked.scored is False
    assert ranked.match_score is None
    assert ranked.data_completeness is None


def test_perfect_match_scores_100():
    plan = SearchPlan(
        keywords=KeywordsPlan(required=["Python", "Django"]),
        min_experience=3,
        max_experience=6,
        current_location=["Bengaluru"],
        designation=["Python Developer"],
    )
    candidate = CandidateResult(
        name="Jane Doe",
        title="Python Developer",
        location="Bengaluru",
        skills=["Python", "Django"],
        experience="5 yrs",
    )
    ranked = rank_candidate(candidate, plan)
    assert ranked.scored is True
    assert ranked.match_score == 100.0
    assert ranked.data_completeness == 100.0
    assert set(ranked.matched_requirements) >= {"Python", "Django", "Bengaluru", "Python Developer"}
    assert ranked.missing_requirements == []
    assert ranked.unavailable_info == []


def test_missing_candidate_data_is_unavailable_not_zero():
    """Plan requires location, but the extractor never got candidate.location —
    this must show up as 'unavailable', and must NOT drag the score down as if
    the candidate failed a location requirement they were never actually tested on."""
    plan = SearchPlan(
        keywords=KeywordsPlan(required=["Python"]),
        current_location=["Bengaluru"],
    )
    candidate = CandidateResult(name="Jane Doe", skills=["Python"], location=None)
    ranked = rank_candidate(candidate, plan)

    assert ranked.scored is True
    assert ranked.match_score == 100.0  # scored only on the skills dimension, which matched fully
    assert ranked.data_completeness == 50.0  # 1 of 2 requested dimensions had data
    assert any("location" in u for u in ranked.unavailable_info)
    assert "Bengaluru" not in ranked.missing_requirements, "must not claim location was checked and failed"


def test_partial_skill_match_and_missing_required_skill_is_reported():
    plan = SearchPlan(keywords=KeywordsPlan(required=["Python", "Kubernetes"]))
    candidate = CandidateResult(name="Jane Doe", skills=["Python"])
    ranked = rank_candidate(candidate, plan)
    assert ranked.match_score == 50.0
    assert "Python" in ranked.matched_requirements
    assert "Kubernetes" in ranked.missing_requirements


def test_experience_outside_range_scores_below_100_but_not_fabricated_when_unparseable():
    plan = SearchPlan(min_experience=5, max_experience=8)
    within = rank_candidate(CandidateResult(name="A", experience="6 yrs"), plan)
    assert within.match_score == 100.0

    below = rank_candidate(CandidateResult(name="B", experience="2 yrs"), plan)
    assert below.match_score is not None and below.match_score < 100.0
    assert any("2.0 yrs" in m for m in below.missing_requirements)

    unparseable = rank_candidate(CandidateResult(name="C", experience="Fresher"), plan)
    assert unparseable.scored is False, "experience requested but unparseable -> unavailable, not a fabricated 0"
    assert any("experience" in u for u in unparseable.unavailable_info)


def test_rank_candidates_sorts_scored_desc_and_puts_unscored_last():
    plan = SearchPlan(keywords=KeywordsPlan(required=["Python"]))
    high = CandidateResult(name="High", skills=["Python"])
    low = CandidateResult(name="Low", skills=["Java"])
    unscored = CandidateResult(name="NoSkillsData")  # empty skills -> unavailable, not scored on this dim
    ranked = rank_candidates([low, unscored, high], plan)
    names = [r.name for r in ranked]
    assert names[0] == "High"
    assert names[-1] == "NoSkillsData"


def test_rank_candidates_with_no_active_plan_returns_all_unscored():
    candidates = [CandidateResult(name="A"), CandidateResult(name="B")]
    ranked = rank_candidates(candidates, None)
    assert all(r.scored is False and r.match_score is None for r in ranked)
