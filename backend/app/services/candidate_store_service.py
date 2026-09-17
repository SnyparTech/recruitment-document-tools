import re
from typing import List
from app.schemas.candidate_result import CandidateResult


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def candidate_dedup_key(candidate: CandidateResult) -> str:
    """
    Deterministic dedup key, in preference order:
      1. profile_url — the strongest signal, a direct link to one candidate.
      2. resdex_candidate_id — Resdex's own identifier, if the extractor found one.
      3. normalized(name + company) — best-effort fallback. Deliberately includes
         company (not name alone) so two different candidates who happen to share
         a common name are not silently merged into one.
      4. normalized(name) alone, only if company is unknown — last resort; two
         same-named candidates with no other distinguishing data scraped will
         collide here, which is an accepted, documented limitation rather than
         a guess dressed up as certainty.
    """
    if candidate.profile_url:
        return f"url:{candidate.profile_url.strip().lower()}"
    if candidate.resdex_candidate_id:
        return f"id:{candidate.resdex_candidate_id.strip().lower()}"
    if candidate.company:
        return f"namecompany:{_normalize(candidate.name)}:{_normalize(candidate.company)}"
    return f"name:{_normalize(candidate.name)}"


def merge_candidates(existing: List[CandidateResult], new: List[CandidateResult]) -> List[CandidateResult]:
    """
    Merges a newly-scraped batch into the existing stored list, deduplicating
    by candidate_dedup_key. On collision, the newer record replaces the older
    one (a later page-load may have more complete data than an earlier one).
    """
    by_key = {candidate_dedup_key(c): c for c in existing}
    for c in new:
        by_key[candidate_dedup_key(c)] = c
    return list(by_key.values())
