from typing import Dict, List
from app.models.requirement import GeneratedQuery, ParsedRequirement

ROLE_EXPANSIONS: Dict[str, List[str]] = {
    "AI/ML Engineer": [
        "AI Engineer",
        "ML Engineer",
        "Machine Learning Engineer",
        "Artificial Intelligence Engineer",
    ],
    "Machine Learning Engineer": [
        "ML Engineer",
        "AI Engineer",
        "AI/ML Engineer",
        "Data Scientist",
    ],
    "Python Developer": [
        "Python Engineer",
        "Python Backend Developer",
        "Backend Developer",
        "Software Engineer",
    ],
    "Full Stack Developer": [
        "Full Stack Engineer",
        "Software Engineer",
        "Full Stack Web Developer",
    ],
    "Data Scientist": [
        "Machine Learning Scientist",
        "AI Scientist",
        "Data Science Specialist",
    ],
}


class SearchQueryGenerator:
    """
    Generates clean search query parameters and expanded keyword sets
    from structured ParsedRequirement objects.
    """

    def generate(self, parsed: ParsedRequirement) -> GeneratedQuery:
        """
        Synthesizes a clean search query and structured query filters.
        """
        role_kw = self._expand_role_keywords(parsed.role)
        skill_kw = list(parsed.required_skills)

        # Build clean primary query (avoid generic fluff words)
        query_terms: List[str] = []
        if parsed.role:
            # Clean compound punctuation e.g. "AI/ML" -> "AI ML"
            cleaned_role = parsed.role.replace("/", " ")
            query_terms.append(cleaned_role)
        for s in parsed.required_skills:
            if s not in query_terms:
                query_terms.append(s)

        primary_query = " ".join(query_terms) if query_terms else "Software Engineer"

        min_exp = parsed.experience.min_years if parsed.experience else None
        max_exp = parsed.experience.max_years if parsed.experience else None

        return GeneratedQuery(
            primary_query=primary_query,
            role_keywords=role_kw,
            skill_keywords=skill_kw,
            location=parsed.location,
            min_experience=min_exp,
            max_experience=max_exp,
        )

    def _expand_role_keywords(self, role: str | None) -> List[str]:
        """Generate expanded variations of the target role."""
        if not role:
            return []

        expanded = ROLE_EXPANSIONS.get(role, [])
        result = [role]
        for exp in expanded:
            if exp not in result:
                result.append(exp)
        return result
