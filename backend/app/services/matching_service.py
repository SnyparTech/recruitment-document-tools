import re
from typing import List, Optional, Set, Tuple
from app.models.candidate import CandidateProfile
from app.models.requirement import ParsedRequirement

# Role synonym clusters for semantic similarity
ROLE_CLUSTERS = [
    {
        "ai/ml engineer",
        "ai ml engineer",
        "machine learning engineer",
        "ml engineer",
        "ai engineer",
        "artificial intelligence engineer",
        "data scientist",
        "nlp engineer",
        "deep learning engineer",
    },
    {
        "python developer",
        "python backend developer",
        "python engineer",
        "python software engineer",
        "backend developer",
        "backend engineer",
    },
    {"full stack developer", "full stack engineer", "full stack software engineer"},
    {"frontend developer", "frontend engineer", "react developer", "ui developer"},
    {"devops engineer", "cloud engineer", "site reliability engineer", "sre"},
    {"data engineer", "big data engineer", "pyspark developer"},
]


class MatchingService:
    """
    Evaluates candidate profiles against parsed recruitment requirements
    using a multi-factor weighted scoring algorithm normalized to 0-100.

    Base Weights:
    - Skills Match:       40%
    - Role Similarity:    20%
    - Experience Match:   15%
    - Location Match:     15%
    - Education Match:    10%
    """

    BASE_WEIGHTS = {
        "skills": 40.0,
        "role": 20.0,
        "experience": 15.0,
        "location": 15.0,
        "education": 10.0,
    }

    def score_candidate(
        self, candidate: CandidateProfile, requirement: ParsedRequirement
    ) -> CandidateProfile:
        """
        Calculates and assigns match_score, matched_skills, and missing_skills
        to the CandidateProfile.
        """
        matched_skills, missing_skills, raw_skill_score = self._score_skills(
            candidate.skills, requirement.required_skills
        )
        raw_role_score = self._score_role(candidate.current_title, requirement.role)
        raw_exp_score = self._score_experience(
            candidate.experience_years, requirement.experience
        )
        raw_loc_score = self._score_location(candidate.location, requirement.location)
        raw_edu_score = self._score_education(candidate.education, requirement.education)

        # Dynamic weight redistribution if education is not specified
        if requirement.education is None:
            # Active weights total = 40 + 20 + 15 + 15 = 90
            active_total = (
                self.BASE_WEIGHTS["skills"]
                + self.BASE_WEIGHTS["role"]
                + self.BASE_WEIGHTS["experience"]
                + self.BASE_WEIGHTS["location"]
            )
            raw_sum = raw_skill_score + raw_role_score + raw_exp_score + raw_loc_score
            normalized_score = (raw_sum / active_total) * 100.0
        else:
            raw_sum = (
                raw_skill_score
                + raw_role_score
                + raw_exp_score
                + raw_loc_score
                + raw_edu_score
            )
            normalized_score = raw_sum

        final_score = round(max(0.0, min(100.0, normalized_score)), 1)

        candidate.match_score = final_score
        candidate.matched_skills = matched_skills
        candidate.missing_skills = missing_skills

        return candidate

    def _normalize_token(self, text: str) -> str:
        """Normalize string token for comparison."""
        return re.sub(r"[\s\-_./]+", "", text.lower())

    def _score_skills(
        self, candidate_skills: List[str], required_skills: List[str]
    ) -> Tuple[List[str], List[str], float]:
        """
        Calculates 40% skills score, matched_skills, and missing_skills.
        """
        if not required_skills:
            return candidate_skills, [], self.BASE_WEIGHTS["skills"]

        cand_norm_map = {self._normalize_token(s): s for s in candidate_skills}
        matched: List[str] = []
        missing: List[str] = []

        for req in required_skills:
            req_norm = self._normalize_token(req)
            found = False
            for c_norm in cand_norm_map:
                if req_norm == c_norm or (len(req_norm) > 3 and req_norm in c_norm) or (len(c_norm) > 3 and c_norm in req_norm):
                    matched.append(req)
                    found = True
                    break
            if not found:
                missing.append(req)

        ratio = len(matched) / len(required_skills)
        score = ratio * self.BASE_WEIGHTS["skills"]
        return matched, missing, score

    def _score_role(self, candidate_title: str, required_role: Optional[str]) -> float:
        """
        Calculates 20% role similarity score using semantic clustering & token overlap.
        """
        if not required_role:
            return self.BASE_WEIGHTS["role"]

        c_title = candidate_title.lower().strip()
        r_role = required_role.lower().strip()

        # Exact match
        if c_title == r_role:
            return self.BASE_WEIGHTS["role"]

        # Check cluster similarity
        for cluster in ROLE_CLUSTERS:
            c_in = any(role_term in c_title for role_term in cluster)
            r_in = any(role_term in r_role for role_term in cluster)
            if c_in and r_in:
                # Substring/exact in cluster
                return self.BASE_WEIGHTS["role"] * 0.95

        # Substring overlap
        if r_role in c_title or c_title in r_role:
            return self.BASE_WEIGHTS["role"] * 0.90

        # Token intersection
        c_tokens = set(re.findall(r"\w+", c_title)) - {"a", "an", "the", "in", "of", "and"}
        r_tokens = set(re.findall(r"\w+", r_role)) - {"a", "an", "the", "in", "of", "and"}

        if not r_tokens:
            return self.BASE_WEIGHTS["role"]

        common = c_tokens.intersection(r_tokens)
        ratio = len(common) / len(r_tokens)
        return ratio * self.BASE_WEIGHTS["role"]

    def _score_experience(
        self, candidate_exp: float, exp_constraint: Optional[any]
    ) -> float:
        """
        Calculates 15% experience proximity score.
        """
        if not exp_constraint or (
            exp_constraint.min_years is None and exp_constraint.max_years is None
        ):
            return self.BASE_WEIGHTS["experience"]

        min_y = exp_constraint.min_years
        max_y = exp_constraint.max_years

        # Case 1: Range [min, max]
        if min_y is not None and max_y is not None:
            if min_y <= candidate_exp <= max_y:
                return self.BASE_WEIGHTS["experience"]
            elif candidate_exp < min_y:
                ratio = candidate_exp / max(min_y, 0.5)
                return max(0.0, ratio * self.BASE_WEIGHTS["experience"])
            else:
                # Slightly above max_years
                diff = candidate_exp - max_y
                penalty = min(diff * 1.5, self.BASE_WEIGHTS["experience"] * 0.4)
                return max(0.0, self.BASE_WEIGHTS["experience"] - penalty)

        # Case 2: Minimum only
        if min_y is not None and max_y is None:
            if candidate_exp >= min_y:
                return self.BASE_WEIGHTS["experience"]
            ratio = candidate_exp / max(min_y, 0.5)
            return max(0.0, ratio * self.BASE_WEIGHTS["experience"])

        return self.BASE_WEIGHTS["experience"]

    def _score_location(
        self, candidate_loc: str, required_loc: Optional[str]
    ) -> float:
        """
        Calculates 15% location score with city normalization and region synonyms.
        """
        if not required_loc:
            return self.BASE_WEIGHTS["location"]

        c_loc = candidate_loc.lower().strip()
        r_loc = required_loc.lower().strip()

        if r_loc in ("remote", "any", "hybrid") or c_loc == "remote":
            return self.BASE_WEIGHTS["location"]

        # Normalize "Hyderabad, Telangana" -> contains "hyderabad"
        # "Bangalore" -> contains "bengaluru"
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

        if r_norm in c_norm or c_norm in r_norm:
            return self.BASE_WEIGHTS["location"]

        return 0.0

    def _score_education(
        self, candidate_edu: Optional[str], required_edu: Optional[str]
    ) -> float:
        """
        Calculates 10% educational qualification score.
        """
        if not required_edu:
            return self.BASE_WEIGHTS["education"]

        if not candidate_edu:
            return self.BASE_WEIGHTS["education"] * 0.4

        c_edu = candidate_edu.lower()
        r_edu = required_edu.lower()

        if r_edu in c_edu:
            return self.BASE_WEIGHTS["education"]

        tech_degrees = {"b.tech", "b.e", "be", "mca", "m.tech", "ms", "bs"}
        if any(d in r_edu for d in tech_degrees) and any(d in c_edu for d in tech_degrees):
            return self.BASE_WEIGHTS["education"] * 0.9

        return self.BASE_WEIGHTS["education"] * 0.5
