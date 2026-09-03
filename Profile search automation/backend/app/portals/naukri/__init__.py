from typing import Any, Dict, List
from app.data.mock_candidates import MOCK_CANDIDATES
from app.models.candidate import CandidateProfile
from app.models.requirement import GeneratedQuery, ParsedRequirement
from app.portals.base import BaseCandidatePortal
from app.portals.naukri.scraper import NaukriScraper


class NaukriPortal(BaseCandidatePortal):
    """
    Naukri Candidate Portal Adapter.
    Supports both safe mock mode for local testing and Selenium browser mode for authorized live search.
    """

    def __init__(self, scraper: NaukriScraper = None):
        self.scraper = scraper or NaukriScraper()

    @property
    def portal_name(self) -> str:
        return "naukri"

    def search_candidates(
        self,
        requirement: ParsedRequirement,
        query: GeneratedQuery,
        use_mock: bool = True,
    ) -> List[CandidateProfile]:
        """
        Retrieves candidates from mock dataset or live Selenium search.
        """
        if use_mock:
            return self._load_mock_candidates()
        return self.scraper.search(requirement=requirement, query=query)

    def _load_mock_candidates(self) -> List[CandidateProfile]:
        """
        Constructs CandidateProfile models from the mock candidates repository.
        """
        candidates: List[CandidateProfile] = []
        for item in MOCK_CANDIDATES:
            profile = CandidateProfile(
                id=item["id"],
                name=item["name"],
                current_title=item["current_title"],
                current_company=item.get("current_company"),
                experience_years=float(item["experience_years"]),
                location=item["location"],
                skills=list(item.get("skills", [])),
                education=item.get("education"),
                profile_url=item["profile_url"],
                source="naukri",
                match_score=0.0,
                matched_skills=[],
                missing_skills=[],
            )
            candidates.append(profile)
        return candidates


__all__ = ["NaukriPortal", "NaukriScraper"]
