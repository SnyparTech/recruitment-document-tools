import json
import logging
import re
from typing import Optional
import httpx
from app.core.config import settings
from app.models.requirement import ExperienceRange, ParsedRequirement

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert technical recruitment intelligence parser.
Your task is to analyze the recruiter's natural-language hiring requirement and extract structured recruitment criteria as valid JSON only.

JSON Output Schema:
{
  "role": "<job title / role or null>",
  "required_skills": ["<skill1>", "<skill2>", ...],
  "preferred_skills": ["<skill1>", ...],
  "min_experience_years": <number or null>,
  "max_experience_years": <number or null>,
  "location": "<city name or Remote or null>",
  "education": "<degree qualification or null>"
}

Rules:
1. Normalize skill acronyms (e.g., 'ML' -> 'Machine Learning', 'AI' -> 'Artificial Intelligence', 'NLP' -> 'NLP', 'Postgres' -> 'PostgreSQL', 'TS' -> 'TypeScript', 'JS' -> 'JavaScript', 'GenAI' -> 'Generative AI').
2. Parse numerical experience bounds (e.g. '1-3 years' -> min: 1.0, max: 3.0; '2+ years' -> min: 2.0, max: null).
3. Standardize city locations (e.g., 'Bangalore' -> 'Bengaluru', 'Hyderabad', 'Pune', 'Delhi NCR', 'Remote').
4. Return ONLY valid JSON with no markdown formatting or commentary.
"""


class LLMRequirementParser:
    """
    Parses natural language requirements into structured ParsedRequirement models
    using Groq LLM (e.g. Qwen models like qwen/qwen3.6-27b).
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.GROQ_API_KEY
        self.model = model or settings.GROQ_MODEL
        self.api_url = settings.GROQ_API_URL

    def parse(self, text: str) -> Optional[ParsedRequirement]:
        """
        Calls Groq API with the Qwen model to parse natural-language requirement text.
        """
        if not self.api_key:
            logger.warning("GROQ_API_KEY not configured. Falling back to rule-based parser.")
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Recruiter Requirement:\n\"\"\"{text}\"\"\""},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }

        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.post(self.api_url, headers=headers, json=payload)
                if response.status_code != 200:
                    logger.warning(
                        f"Groq API error {response.status_code}: {response.text}"
                    )
                    return None

                data = response.json()
                content = data["choices"][0]["message"]["content"]
                parsed_json = json.loads(content)

                min_exp = parsed_json.get("min_experience_years")
                max_exp = parsed_json.get("max_experience_years")

                exp_range = None
                if min_exp is not None or max_exp is not None:
                    exp_range = ExperienceRange(
                        min_years=float(min_exp) if min_exp is not None else None,
                        max_years=float(max_exp) if max_exp is not None else None,
                    )

                return ParsedRequirement(
                    role=parsed_json.get("role"),
                    required_skills=parsed_json.get("required_skills", []),
                    preferred_skills=parsed_json.get("preferred_skills", []),
                    experience=exp_range,
                    location=parsed_json.get("location"),
                    education=parsed_json.get("education"),
                )

        except Exception as exc:
            logger.warning(f"Failed to parse requirement using Groq LLM: {exc}")
            return None
