import re
from typing import Dict, List, Optional, Tuple
from app.models.requirement import ExperienceRange, ParsedRequirement

# Comprehensive canonical tech skills & alias mapping
SKILL_ALIASES: Dict[str, str] = {
    "ml": "Machine Learning",
    "machine learning": "Machine Learning",
    "ai": "Artificial Intelligence",
    "artificial intelligence": "Artificial Intelligence",
    "nlp": "NLP",
    "natural language processing": "NLP",
    "llm": "LLM",
    "large language models": "LLM",
    "large language model": "LLM",
    "genai": "Generative AI",
    "generative ai": "Generative AI",
    "gen ai": "Generative AI",
    "dl": "Deep Learning",
    "deep learning": "Deep Learning",
    "python": "Python",
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "js": "JavaScript",
    "javascript": "JavaScript",
    "ts": "TypeScript",
    "typescript": "TypeScript",
    "react": "React",
    "reactjs": "React",
    "react.js": "React",
    "nextjs": "Next.js",
    "next.js": "Next.js",
    "vue": "Vue.js",
    "vuejs": "Vue.js",
    "angular": "Angular",
    "node": "Node.js",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "express": "Express.js",
    "expressjs": "Express.js",
    "java": "Java",
    "spring": "Spring Boot",
    "spring boot": "Spring Boot",
    "springboot": "Spring Boot",
    "golang": "Golang",
    "go": "Golang",
    "rust": "Rust",
    "c++": "C++",
    "cpp": "C++",
    "c#": "C#",
    ".net": ".NET",
    "dotnet": ".NET",
    "ruby": "Ruby",
    "rails": "Ruby on Rails",
    "php": "PHP",
    "laravel": "Laravel",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "sql": "SQL",
    "nosql": "NoSQL",
    "mongodb": "MongoDB",
    "mongo": "MongoDB",
    "cassandra": "Cassandra",
    "dynamodb": "DynamoDB",
    "redis": "Redis",
    "elasticsearch": "ElasticSearch",
    "elastic search": "ElasticSearch",
    "solr": "Solr",
    "kafka": "Kafka",
    "rabbitmq": "RabbitMQ",
    "celery": "Celery",
    "graphql": "GraphQL",
    "rest api": "REST APIs",
    "rest apis": "REST APIs",
    "microservices": "Microservices",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "terraform": "Terraform",
    "ansible": "Ansible",
    "aws": "AWS",
    "azure": "Azure",
    "gcp": "GCP",
    "google cloud": "GCP",
    "git": "Git",
    "github": "GitHub",
    "gitlab": "GitLab",
    "ci/cd": "CI/CD",
    "cicd": "CI/CD",
    "linux": "Linux",
    "spark": "Apache Spark",
    "pyspark": "PySpark",
    "hadoop": "Hadoop",
    "airflow": "Apache Airflow",
    "snowflake": "Snowflake",
    "databricks": "Databricks",
    "dbt": "dbt",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "scipy": "SciPy",
    "scikit-learn": "Scikit-Learn",
    "sklearn": "Scikit-Learn",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "keras": "Keras",
    "opencv": "OpenCV",
    "langchain": "LangChain",
    "llamaindex": "LlamaIndex",
    "huggingface": "HuggingFace",
    "tableau": "Tableau",
    "power bi": "Power BI",
    "powerbi": "Power BI",
}

JOB_ROLES: List[str] = [
    "AI/ML Engineer",
    "AI ML Engineer",
    "AI Engineer",
    "ML Engineer",
    "Machine Learning Engineer",
    "Artificial Intelligence Engineer",
    "Data Scientist",
    "NLP Engineer",
    "Computer Vision Engineer",
    "Deep Learning Engineer",
    "Generative AI Engineer",
    "LLM Engineer",
    "Python Developer",
    "Python Backend Developer",
    "Python Engineer",
    "Senior Python Developer",
    "Senior AI/ML Architect",
    "Full Stack Developer",
    "Full Stack Engineer",
    "Backend Developer",
    "Backend Engineer",
    "Frontend Developer",
    "Frontend Engineer",
    "Software Engineer",
    "Software Development Engineer",
    "SDE",
    "SDE 1",
    "SDE 2",
    "SDE 3",
    "Data Engineer",
    "Big Data Engineer",
    "DevOps Engineer",
    "Cloud Engineer",
    "Site Reliability Engineer",
    "SRE",
    "Java Developer",
    "Golang Developer",
    "iOS Developer",
    "Android Developer",
    "Mobile Developer",
    "QA Engineer",
    "SDET",
]

LOCATIONS: List[str] = [
    "Hyderabad",
    "Bengaluru",
    "Bangalore",
    "Pune",
    "Delhi NCR",
    "Delhi",
    "Noida",
    "Gurgaon",
    "Gurugram",
    "Chennai",
    "Mumbai",
    "Kolkata",
    "Ahmedabad",
    "Kochi",
    "Chandigarh",
    "Jaipur",
    "Indore",
    "Coimbatore",
    "Remote",
    "Hybrid",
]

EDUCATION_DEGREES: List[str] = [
    "B.Tech",
    "B.E",
    "BE",
    "M.Tech",
    "M.E",
    "ME",
    "MCA",
    "BCA",
    "B.Sc",
    "M.Sc",
    "MS",
    "BS",
    "B.Com",
    "MBA",
    "PhD",
    "Doctorate",
    "Bachelor",
    "Master",
]


class RequirementParser:
    """
    Dynamically extracts structured recruitment criteria (role, skills, experience,
    location, education) from ANY natural language hiring prompt using Groq LLM
    (e.g., Qwen models) with automatic fallback to high-precision rule-based parsing.
    """

    def __init__(self, use_llm: bool = True):
        self.use_llm = use_llm
        self._llm_parser = None

    @property
    def llm_parser(self):
        if self._llm_parser is None and self.use_llm:
            try:
                from app.services.llm_parser import LLMRequirementParser
                self._llm_parser = LLMRequirementParser()
            except Exception:
                self._llm_parser = None
        return self._llm_parser

    def parse(self, text: str) -> ParsedRequirement:
        """
        Parse natural-language requirement into structured ParsedRequirement.
        Attempts Groq LLM parsing first, then falls back to rule-based parser.
        """
        if not text or not text.strip():
            return ParsedRequirement()

        cleaned_text = text.strip()

        # Attempt Groq LLM parsing if configured
        if self.llm_parser:
            llm_result = self.llm_parser.parse(cleaned_text)
            if llm_result:
                return llm_result

        # Rule-based fallback parser
        skills = self._extract_skills(cleaned_text)
        role = self._extract_role(cleaned_text, skills)
        exp_range = self._extract_experience(cleaned_text)
        location = self._extract_location(cleaned_text)
        education = self._extract_education(cleaned_text)

        return ParsedRequirement(
            role=role,
            required_skills=skills,
            preferred_skills=[],
            experience=exp_range,
            location=location,
            education=education,
        )

    def _extract_skills(self, text: str) -> List[str]:
        """
        Extracts known and dynamic technical skills from input text.
        """
        extracted: List[str] = []
        lower_text = text.lower()

        # Step 1: Match from taxonomy with alias mapping
        sorted_aliases = sorted(SKILL_ALIASES.keys(), key=len, reverse=True)
        for alias in sorted_aliases:
            canonical = SKILL_ALIASES[alias]
            escaped = re.escape(alias)
            pattern = rf"(?:\b|(?<=\s)){escaped}(?:\b|(?=\s)|$)"
            if re.search(pattern, lower_text):
                if canonical not in extracted:
                    extracted.append(canonical)

        # Step 2: Dynamic extraction for skills explicitly listed e.g. "skills: React, Node, WebRTC"
        skill_section_match = re.search(
            r"(?:skills?|technologies|tools?|tech stack|proficient in|experience with|knowledge of)\s*[:=-]?\s*([a-zA-Z0-9\s,\/\+\#\.\-]+?)(?:\.|$|in\s+[A-Z]|with\s+\d)",
            text,
            re.IGNORECASE,
        )
        if skill_section_match:
            raw_skills = re.split(r"[,|/&]+|\band\b", skill_section_match.group(1))
            for raw_s in raw_skills:
                item = raw_s.strip()
                if item and len(item) > 1 and len(item) < 30:
                    clean_item = SKILL_ALIASES.get(item.lower(), item)
                    if clean_item not in extracted and clean_item.lower() not in [
                        "experience", "years", "year", "yrs", "in", "and", "or", "for", "with"
                    ]:
                        extracted.append(clean_item)

        return extracted

    def _extract_role(self, text: str, detected_skills: List[str]) -> Optional[str]:
        """Dynamically identify target role or title."""
        lower_text = text.lower()

        # Compound AI/ML role match
        if re.search(r"\bai[\s/_-]*ml\s+engineers?\b", lower_text):
            return "AI/ML Engineer"

        # Explicit roles from taxonomy
        for role in sorted(JOB_ROLES, key=len, reverse=True):
            escaped = re.escape(role.lower())
            if re.search(rf"\b{escaped}s?\b", lower_text):
                return role

        # Dynamic regex extraction: "find/looking for/hiring a <Role> in/with"
        match = re.search(
            r"(?:find|looking for|hiring|need|require|seeking)\s+(?:a|an)?\s*([a-zA-Z\s\/\+]+?)\s+(?:in|with|having|for|who|\d)",
            text,
            re.IGNORECASE,
        )
        if match:
            candidate_role = match.group(1).strip()
            if len(candidate_role.split()) <= 4 and candidate_role.lower() not in [
                "candidate", "someone", "profile", "engineer", "developer"
            ]:
                return candidate_role.title()

        # Fallback to primary skill + Developer
        if detected_skills:
            return f"{detected_skills[0]} Developer"

        return "Software Professional"

    def _extract_experience(self, text: str) -> Optional[ExperienceRange]:
        """Extract dynamic numerical experience constraints."""
        lower_text = text.lower()

        # Range pattern (e.g. 1-3 years, 2 to 5 yrs)
        range_match = re.search(
            r"(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?|yr)",
            lower_text,
        )
        if range_match:
            min_y = float(range_match.group(1))
            max_y = float(range_match.group(2))
            return ExperienceRange(min_years=min_y, max_years=max_y)

        # Plus pattern (e.g. 2+ years, 3+ yrs)
        plus_match = re.search(
            r"(\d+(?:\.\d+)?)\s*\+\s*(?:years?|yrs?|yr)",
            lower_text,
        )
        if plus_match:
            min_y = float(plus_match.group(1))
            return ExperienceRange(min_years=min_y, max_years=None)

        # Min pattern (e.g. min 3 years, at least 2 yrs)
        min_match = re.search(
            r"(?:min|minimum|at least)\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?|yr)",
            lower_text,
        )
        if min_match:
            min_y = float(min_match.group(1))
            return ExperienceRange(min_years=min_y, max_years=None)

        # Single value (e.g. 2 years experience)
        single_match = re.search(
            r"(\d+(?:\.\d+)?)\s*(?:years?|yrs?|yr)",
            lower_text,
        )
        if single_match:
            min_y = float(single_match.group(1))
            return ExperienceRange(min_years=min_y, max_years=None)

        # Fresher
        if re.search(r"\b(fresher|entry\s*level|intern)\b", lower_text):
            return ExperienceRange(min_years=0.0, max_years=1.0)

        return None

    def _extract_location(self, text: str) -> Optional[str]:
        """Extract city or geographic location."""
        lower_text = text.lower()
        for loc in LOCATIONS:
            pattern = rf"\b{re.escape(loc.lower())}\b"
            if re.search(pattern, lower_text):
                if loc.lower() == "bangalore":
                    return "Bengaluru"
                return loc

        # Context pattern: "in <City>", "based out of <City>"
        loc_pattern = re.search(
            r"(?:in|at|location:|based (?:in|out of))\s+([A-Za-z]+)",
            text,
            re.IGNORECASE,
        )
        if loc_pattern:
            candidate = loc_pattern.group(1).strip().capitalize()
            if candidate.lower() not in [
                "python", "fastapi", "experience", "years", "skills", "hyderabad", "degree"
            ]:
                return candidate

        return None

    def _extract_education(self, text: str) -> Optional[str]:
        """Extract qualification or degree."""
        lower_text = text.lower()
        for edu in EDUCATION_DEGREES:
            pattern = rf"\b{re.escape(edu.lower())}\b"
            if re.search(pattern, lower_text):
                return edu
        return None
