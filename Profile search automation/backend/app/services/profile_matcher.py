import re
from typing import List, Optional, Set, Tuple
from app.models.profile import CandidateProfile
from app.models.requirement import ParsedRequirement


class ProfileMatcher:
    """
    Evaluates candidate profiles against parsed recruitment requirements
    using a multi-factor weighted scoring algorithm normalized to 0-100.

    Weight Distribution:
    - Skills Match:       40%
    - Job Title / Role:   20%
    - Experience Match:   15%
    - Location Match:     15%
    - Education Match:    10%
    """

    SKILL_WEIGHT: float = 40.0
    ROLE_WEIGHT: float = 20.0
    EXP_WEIGHT: float = 15.0
    LOC_WEIGHT: float = 15.0
    EDU_WEIGHT: float = 10.0

    def score_profile(
        self, profile: CandidateProfile, requirement: ParsedRequirement
    ) -> CandidateProfile:
        """
        Calculates and updates match_score, matched_skills, and missing_skills
        for the given candidate profile.
        """
        matched_skills, missing_skills, skill_score = self._calculate_skills_score(
            profile.skills, requirement.skills
        )
        role_score = self._calculate_role_score(profile.current_title, requirement.role)
        exp_score = self._calculate_experience_score(
            profile.experience,
            requirement.min_experience_years,
            requirement.max_experience_years,
        )
        loc_score = self._calculate_location_score(profile.location, requirement.location)
        edu_score = self._calculate_education_score(profile.education, requirement.education)

        total_score = skill_score + role_score + exp_score + loc_score + edu_score
        normalized_score = round(max(0.0, min(100.0, total_score)), 1)

        profile.match_score = normalized_score
        profile.matched_skills = matched_skills
        profile.missing_skills = missing_skills

        return profile

    def _normalize_skill_token(self, skill: str) -> str:
        """Standardize skill names for consistent matching."""
        s = skill.strip().lower()
        s = re.sub(r"[\s\-_.]+", "", s)
        return s

    def _calculate_skills_score(
        self, candidate_skills: List[str], required_skills: List[str]
    ) -> Tuple[List[str], List[str], float]:
        """
        Computes 40-point skills match score, matched_skills, and missing_skills.
        """
        if not required_skills:
            # If no skills explicitly required, give full skill credit
            return candidate_skills, [], self.SKILL_WEIGHT

        cand_norm = {self._normalize_skill_token(s): s for s in candidate_skills}
        matched: List[str] = []
        missing: List[str] = []

        for req_s in required_skills:
            req_norm = self._normalize_skill_token(req_s)
            found = False
            # Direct or substring match in candidate skills
            for c_norm, orig_cand_s in cand_norm.items():
                if req_norm == c_norm or (len(req_norm) > 3 and req_norm in c_norm) or (len(c_norm) > 3 and c_norm in req_norm):
                    matched.append(req_s)
                    found = True
                    break
            if not found:
                missing.append(req_s)

        ratio = len(matched) / len(required_skills)
        score = ratio * self.SKILL_WEIGHT
        return matched, missing, score

    def _calculate_role_score(
        self, candidate_title: str, required_role: Optional[str]
    ) -> float:
        """
        Computes 20-point job role relevance score using token and substring overlap.
        """
        if not required_role:
            return self.ROLE_WEIGHT

        c_title = candidate_title.lower().strip()
        r_role = required_role.lower().strip()

        if c_title == r_role:
            return self.ROLE_WEIGHT

        if r_role in c_title or c_title in r_role:
            return self.ROLE_WEIGHT * 0.95

        # Token overlap analysis
        c_tokens = set(re.findall(r"\w+", c_title))
        r_tokens = set(re.findall(r"\w+", r_role))

        # Filter generic non-role stop words
        stop = {"a", "an", "the", "in", "of", "and", "with", "for", "to"}
        c_tokens -= stop
        r_tokens -= stop

        if not r_tokens:
            return self.ROLE_WEIGHT

        common = c_tokens.intersection(r_tokens)
        overlap_ratio = len(common) / len(r_tokens)

        return overlap_ratio * self.ROLE_WEIGHT

    def _parse_experience_years(self, exp_str: str) -> float:
        """Extract numerical years from experience string e.g. '2.5 years'."""
        match = re.search(r"(\d+(?:\.\d+)?)", exp_str)
        if match:
            return float(match.group(1))
        return 0.0

    def _calculate_experience_score(
        self,
        candidate_exp_str: str,
        min_years: Optional[float],
        max_years: Optional[float],
    ) -> float:
        """
        Computes 15-point experience proximity score.
        """
        cand_years = self._parse_experience_years(candidate_exp_str)

        if min_years is None and max_years is None:
            return self.EXP_WEIGHT

        # Case 1: Minimum experience specified (e.g. 2+ years)
        if min_years is not None and max_years is None:
            if cand_years >= min_years:
                return self.EXP_WEIGHT
            # Proportional credit if candidate is close
            ratio = cand_years / max(min_years, 1.0)
            return max(0.0, ratio * self.EXP_WEIGHT)

        # Case 2: Range specified (e.g. 2 - 5 years)
        if min_years is not None and max_years is not None:
            if min_years <= cand_years <= max_years:
                return self.EXP_WEIGHT
            elif cand_years < min_years:
                ratio = cand_years / max(min_years, 1.0)
                return max(0.0, ratio * self.EXP_WEIGHT)
            else:
                # Slightly overqualified
                excess = cand_years - max_years
                penalty = min(excess * 1.5, self.EXP_WEIGHT * 0.5)
                return max(0.0, self.EXP_WEIGHT - penalty)

        return self.EXP_WEIGHT

    def _calculate_location_score(
        self, candidate_location: str, required_location: Optional[str]
    ) -> float:
        """
        Computes 15-point location compatibility score.
        """
        if not required_location:
            return self.LOC_WEIGHT

        c_loc = candidate_location.lower().strip()
        r_loc = required_location.lower().strip()

        # Handle Bengaluru / Bangalore equivalence
        synonyms = {
            "bangalore": "bengaluru",
            "bengaluru": "bengaluru",
            "delhi": "delhi ncr",
            "noida": "delhi ncr",
            "gurgaon": "delhi ncr",
            "gurugram": "delhi ncr",
        }

        c_norm = synonyms.get(c_loc, c_loc)
        r_norm = synonyms.get(r_loc, r_loc)

        if r_norm in ("remote", "any", "hybrid") or c_norm == "remote":
            return self.LOC_WEIGHT

        if c_norm == r_norm or r_norm in c_norm or c_norm in r_norm:
            return self.LOC_WEIGHT

        # Partial credit for other locations
        return 0.0

    def _calculate_education_score(
        self, candidate_education: Optional[str], required_education: Optional[str]
    ) -> float:
        """
        Computes 10-point educational qualification score.
        """
        if not required_education:
            return self.EDU_WEIGHT

        if not candidate_education:
            return self.EDU_WEIGHT * 0.5

        c_edu = candidate_education.lower()
        r_edu = required_education.lower()

        # Direct mention
        if r_edu in c_edu:
            return self.EDU_WEIGHT

        # Equivalent technical degree checks (B.Tech / B.E / MCA / BS / MS)
        tech_degrees = {"b.tech", "b.e", "be", "mca", "m.tech", "bs", "ms"}
        r_is_tech = any(d in r_edu for d in tech_degrees)
        c_is_tech = any(d in c_edu for d in tech_degrees)

        if r_is_tech and c_is_tech:
            return self.EDU_WEIGHT * 0.9

        return self.EDU_WEIGHT * 0.5
