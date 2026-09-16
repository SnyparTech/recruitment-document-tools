import logging
import re
from typing import List, Optional
from playwright.sync_api import Locator
from app.models.candidate import CandidateProfile
from app.portals.naukri.selectors import NaukriSelectors

logger = logging.getLogger(__name__)


class NaukriExtractor:
    """
    Parses candidate profile attributes from search result DOM elements.
    Designed with high fault tolerance so missing optional fields do not fail the search.
    """

    def extract_from_card(
        self, card: Locator, index: int = 1
    ) -> Optional[CandidateProfile]:
        """
        Extracts a single CandidateProfile from a candidate result card element.
        """
        try:
            cand_id = f"nk_live_{index}"
            name = self._safe_extract_text(card, NaukriSelectors.CANDIDATE_NAME) or f"Candidate {index}"
            current_title = self._safe_extract_text(card, NaukriSelectors.TITLE) or "Software Professional"
            exp_text = self._safe_extract_text(card, NaukriSelectors.EXPERIENCE) or "0"
            experience_years = self._parse_experience_years(exp_text)
            location = self._safe_extract_text(card, NaukriSelectors.LOCATION) or "Not Specified"
            current_company = self._safe_extract_text(card, NaukriSelectors.CURRENT_COMPANY)
            education = self._safe_extract_text(card, NaukriSelectors.EDUCATION)
            skills = self._extract_skills(card)
            profile_url = self._extract_link(card, NaukriSelectors.PROFILE_LINK) or f"https://www.naukri.com/candidate/{cand_id}"

            return CandidateProfile(
                id=cand_id,
                name=name,
                current_title=current_title,
                current_company=current_company,
                experience_years=experience_years,
                location=location,
                skills=skills,
                education=education,
                profile_url=profile_url,
                source="naukri",
                match_score=0.0,
                matched_skills=[],
                missing_skills=[],
            )
        except Exception as exc:
            logger.warning(f"Failed to extract candidate card {index}: {exc}")
            return None

    def _safe_extract_text(
        self, element: Locator, selector: Optional[str]
    ) -> Optional[str]:
        """Safely extract trimmed text from sub-element if selector is provided."""
        if not selector:
            return None
        try:
            sub_el = self._resolve_locator(element, selector)
            text = sub_el.text_content() or ""
            text = text.strip()
            return text if text else None
        except Exception:
            return None

    def _extract_link(
        self, element: Locator, selector: Optional[str]
    ) -> Optional[str]:
        """Safely extract href attribute from link element."""
        if not selector:
            return None
        try:
            sub_el = self._resolve_locator(element, selector)
            return sub_el.get_attribute("href")
        except Exception:
            return None

    def _extract_skills(self, element: Locator) -> List[str]:
        """Extracts list of skill tags from container or pill elements."""
        skills: List[str] = []
        if NaukriSelectors.SKILL_ITEM:
            try:
                skill_els = self._resolve_locator_all(element, NaukriSelectors.SKILL_ITEM)
                for i in range(skill_els.count()):
                    s = skill_els.nth(i)
                    txt = (s.text_content() or "").strip()
                    if txt and txt not in skills:
                        skills.append(txt)
            except Exception:
                pass

        if not skills and NaukriSelectors.SKILLS_CONTAINER:
            text = self._safe_extract_text(element, NaukriSelectors.SKILLS_CONTAINER)
            if text:
                skills = [s.strip() for s in re.split(r"[,|•\n]+", text) if s.strip()]

        return skills

    def _parse_experience_years(self, text: str) -> float:
        """Parses experience text (e.g., '2.5 yrs', '3 yrs 4 months') to float."""
        match = re.search(r"(\d+(?:\.\d+)?)", text)
        if match:
            return float(match.group(1))
        return 0.0

    @staticmethod
    def _resolve_locator(parent: Locator, selector: str) -> Locator:
        """Resolves a CSS or XPath selector relative to a parent locator."""
        if selector.startswith("//") or selector.startswith("("):
            return parent.locator(f"xpath={selector}")
        return parent.locator(selector).first

    @staticmethod
    def _resolve_locator_all(parent: Locator, selector: str) -> Locator:
        """Resolves a CSS or XPath selector returning all matches relative to a parent locator."""
        if selector.startswith("//") or selector.startswith("("):
            return parent.locator(f"xpath={selector}")
        return parent.locator(selector)
