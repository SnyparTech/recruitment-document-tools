from typing import List, Tuple
from app.models.candidate import CandidateProfile
from app.models.requirement import ParsedRequirement
from app.services.matching_service import MatchingService


class RankingService:
    """
    Evaluates, ranks, and paginates candidate profiles based on dynamic match scores.
    """

    def __init__(self, matcher: MatchingService = None):
        self.matcher = matcher or MatchingService()

    def rank_candidates(
        self,
        candidates: List[CandidateProfile],
        requirement: ParsedRequirement,
        limit: int = 10,
        offset: int = 0,
    ) -> Tuple[List[CandidateProfile], int]:
        """
        Calculates match scores for all candidates, sorts in descending order,
        and returns the paginated batch of candidates (e.g. 1-10, 11-20, etc.).

        :param candidates: List of candidate profiles from portal or pool.
        :param requirement: Parsed recruitment requirement.
        :param limit: Number of candidates per page (max 10).
        :param offset: Number of candidates to skip for pagination (0, 10, 20...).
        :return: Tuple of (paged_candidates, total_candidates_found).
        """
        total_found = len(candidates)
        if not candidates:
            return [], 0

        # Score every candidate profile dynamically
        scored: List[CandidateProfile] = []
        for cand in candidates:
            scored_cand = self.matcher.score_candidate(cand, requirement)
            scored.append(scored_cand)

        # Sort: match_score DESC, experience_years DESC as tie-breaker
        sorted_candidates = sorted(
            scored,
            key=lambda c: (c.match_score, c.experience_years),
            reverse=True,
        )

        effective_limit = min(limit, 10)
        start_idx = max(0, offset)
        end_idx = start_idx + effective_limit

        paged_candidates = sorted_candidates[start_idx:end_idx]

        return paged_candidates, total_found
