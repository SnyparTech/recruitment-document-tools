import re
from typing import List, Optional, Tuple
from app.schemas.candidate_result import CandidateResult, RankedCandidate
from app.schemas.search_plan import SearchPlan

# Base weights among the four dimensions this service can compute from the
# current SearchPlan + CandidateResult shapes. Education is deliberately
# excluded: SearchPlan.ug_qualification/pg_qualification are enum toggles
# ("Any UG qualification" / "Specific UG qualification" / "No UG qualification"),
# not a comparable target string, so there is nothing meaningful to score a
# candidate's free-text `education` field against. Fabricating an education
# score here would violate the "no false precision" requirement, so it's
# omitted rather than guessed.
BASE_WEIGHTS = {
    "skills": 45.0,
    "role": 20.0,
    "experience": 20.0,
    "location": 15.0,
}


def _tokens_match(needle: str, haystack: str) -> bool:
    """
    True if `needle` is present in `haystack` as a whole word/phrase, not a
    bare substring. Plain substring containment (the old behavior) produced
    false positives for short skills/designations — e.g. required skill "AI"
    normalized to "ai" would match candidate skill "Maintenance" ("m-AI-
    ntenance" contains "ai"), or "R" would match "HR", "Marketing", etc.
    This is the root cause behind reported "wrong" ranking: candidates
    getting matched_requirements credit for skills/roles they don't have.
    Word-boundary regex on the *lowercased* (not de-spaced) text avoids that,
    while still matching multi-word phrases like "machine learning" whole.
    """
    needle = (needle or "").strip().lower()
    haystack = (haystack or "").strip().lower()
    if not needle or not haystack:
        return False
    if needle == haystack:
        return True
    # Lookbehind blocks mid-word matches on both sides (no "ai" inside
    # "maintenance"). Lookahead only blocks a following LETTER, not a digit,
    # so versioned skills still match their base name ("Python" ~ "Python3",
    # "HTML" ~ "HTML5") without opening the door to "java" matching
    # "javascript".
    pattern = r"(?<![a-z0-9])" + re.escape(needle) + r"(?![a-z])"
    if re.search(pattern, haystack):
        return True
    # Reverse direction too (candidate skill phrase fully contains needle as a
    # word), and the symmetric case where haystack is a whole word inside needle
    # (e.g. required "Full Stack Developer" vs candidate title "Developer").
    pattern2 = r"(?<![a-z0-9])" + re.escape(haystack) + r"(?![a-z])"
    return bool(re.search(pattern2, needle))


def parse_experience_years(raw: Optional[str]) -> Optional[float]:
    """Best-effort parse of a raw scraped experience string (e.g. '6 yrs 2 months')
    into a float years value. Returns None (not 0) if it can't confidently parse —
    the caller must treat that as "unavailable", not "zero experience"."""
    if not raw:
        return None
    if re.search(r"\bfresher\b", raw, re.IGNORECASE):
        return 0.0
    match = re.search(r"(\d{1,2}(?:\.\d{1,2})?)\s*(?:yrs?|years?)", raw, re.IGNORECASE)
    if not match:
        return None
    years = float(match.group(1))
    month_match = re.search(r"(\d{1,2})\s*(?:months?|mos?)", raw, re.IGNORECASE)
    if month_match:
        years += float(month_match.group(1)) / 12.0
    return round(years, 2)


def _score_skills(candidate_skills: List[str], required: List[str], preferred: List[str]) -> Tuple[Optional[float], List[str], List[str]]:
    if not required and not preferred:
        return None, [], []  # not a plan requirement — not applicable
    if not candidate_skills:
        return None, [], []  # plan requires it, but we have no data — caller marks unavailable

    matched, missing = [], []

    def _check(skill_list):
        hits = 0
        for s in skill_list:
            if any(_tokens_match(s, cs) for cs in candidate_skills):
                matched.append(s)
                hits += 1
            else:
                missing.append(s)
        return hits

    req_hits = _check(required)
    pref_hits = _check(preferred)

    req_score = (req_hits / len(required) * 100) if required else None
    pref_score = (pref_hits / len(preferred) * 100) if preferred else None

    if req_score is not None and pref_score is not None:
        score = req_score * 0.7 + pref_score * 0.3
    else:
        score = req_score if req_score is not None else pref_score

    return score, matched, missing


def _score_role(candidate_title: Optional[str], designations: List[str]) -> Tuple[Optional[float], List[str], List[str]]:
    if not designations:
        return None, [], []
    if not candidate_title:
        return None, [], []

    matched, missing = [], []
    for d in designations:
        if _tokens_match(d, candidate_title):
            matched.append(d)
        else:
            missing.append(d)

    score = 100.0 if matched else 0.0
    return score, matched, missing


def _score_experience(candidate_experience_raw: Optional[str], min_exp: Optional[float], max_exp: Optional[float]) -> Tuple[Optional[float], List[str], List[str]]:
    if min_exp is None and max_exp is None:
        return None, [], []

    years = parse_experience_years(candidate_experience_raw)
    if years is None:
        return None, [], []  # plan requires it, but couldn't parse candidate's experience — unavailable

    label = f"Experience {min_exp or 0}-{max_exp or '∞'} yrs (candidate: {years} yrs)"
    lo = min_exp if min_exp is not None else 0
    hi = max_exp if max_exp is not None else float("inf")

    if lo <= years <= hi:
        return 100.0, [label], []

    distance = (lo - years) if years < lo else (years - hi)
    score = max(0.0, 100.0 - distance * 20.0)  # -20 points per year outside range, floor 0
    return score, [], [label]


def _score_location(candidate_location: Optional[str], target_locations: Optional[List[str]]) -> Tuple[Optional[float], List[str], List[str]]:
    if not target_locations:
        return None, [], []
    if not candidate_location:
        return None, [], []

    matched, missing = [], []
    for loc in target_locations:
        if _tokens_match(loc, candidate_location):
            matched.append(loc)
        else:
            missing.append(loc)

    score = 100.0 if matched else 0.0
    return score, matched, missing


def rank_candidate(candidate: CandidateResult, plan: SearchPlan) -> RankedCandidate:
    required_skills = (plan.keywords.required if plan.keywords else []) or []
    preferred_skills = (plan.keywords.preferred if plan.keywords else []) or []

    components = {
        "skills": _score_skills(candidate.skills, required_skills, preferred_skills),
        "role": _score_role(candidate.title, plan.designation or []),
        "experience": _score_experience(candidate.experience, plan.min_experience, plan.max_experience),
        "location": _score_location(candidate.location, plan.current_location),
    }

    applicable = {k: v for k, v in components.items() if v[0] is not None}
    # A dimension the plan asked about (has a requirement) but scored None because
    # candidate data was missing is "unavailable", distinct from "not applicable".
    requested_dims = {
        "skills": bool(required_skills or preferred_skills),
        "role": bool(plan.designation),
        "experience": plan.min_experience is not None or plan.max_experience is not None,
        "location": bool(plan.current_location),
    }
    unavailable_dims = [k for k, requested in requested_dims.items() if requested and k not in applicable]

    matched_requirements: List[str] = []
    missing_requirements: List[str] = []
    for key, (_score, matched, missing) in applicable.items():
        matched_requirements.extend(matched)
        missing_requirements.extend(missing)

    unavailable_info = [f"{dim}: candidate data not extracted, could not be scored" for dim in unavailable_dims]

    total_requested = sum(1 for requested in requested_dims.values() if requested)
    data_completeness = (len(applicable) / total_requested * 100) if total_requested > 0 else None

    if not applicable:
        return RankedCandidate(
            **candidate.model_dump(),
            scored=False,
            match_score=None,
            data_completeness=data_completeness,
            matched_requirements=[],
            missing_requirements=[],
            unavailable_info=unavailable_info,
        )

    total_weight = sum(BASE_WEIGHTS[k] for k in applicable)
    weighted_score = sum(BASE_WEIGHTS[k] * applicable[k][0] for k in applicable) / total_weight

    return RankedCandidate(
        **candidate.model_dump(),
        scored=True,
        match_score=round(weighted_score, 1),
        data_completeness=round(data_completeness, 1) if data_completeness is not None else None,
        matched_requirements=matched_requirements,
        missing_requirements=missing_requirements,
        unavailable_info=unavailable_info,
    )


def rank_candidates(candidates: List[CandidateResult], plan: Optional[SearchPlan]) -> List[RankedCandidate]:
    """
    Ranks all candidates against `plan`. If plan is None, returns all candidates
    unscored (scored=False) rather than fabricating a ranking against nothing.
    Sorted by match_score descending; unscored candidates sort last, in their
    original order (not arbitrarily penalized to 0, since "unscored" != "0% match").
    """
    if plan is None:
        return [
            RankedCandidate(**c.model_dump(), scored=False, match_score=None, data_completeness=None)
            for c in candidates
        ]

    ranked = [rank_candidate(c, plan) for c in candidates]
    ranked.sort(key=lambda r: (r.match_score is None, -(r.match_score or 0)))
    return ranked
