from abc import ABC, abstractmethod
from typing import List
from app.models.candidate import CandidateProfile
from app.models.requirement import GeneratedQuery, ParsedRequirement


class BaseCandidatePortal(ABC):
    """
    Abstract base class for candidate job portal integrations.
    Allows seamlessly plugging in new portals (LinkedIn, Indeed, Foundit, etc.)
    without changing requirement parsing, matching, or ranking logic.
    """

    @property
    @abstractmethod
    def portal_name(self) -> str:
        """Identifier name of the portal."""
        pass

    @abstractmethod
    def search_candidates(
        self,
        requirement: ParsedRequirement,
        query: GeneratedQuery,
        use_mock: bool = True,
    ) -> List[CandidateProfile]:
        """
        Search and retrieve candidate profiles from the portal.

        :param requirement: Parsed recruitment requirement.
        :param query: Synthesized query parameters.
        :param use_mock: If True, uses the safe mock candidate data layer.
        :return: List of normalized CandidateProfile instances.
        """
        pass
