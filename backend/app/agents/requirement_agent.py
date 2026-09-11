import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx
from app.core.config import settings
from app.schemas.search_plan import (
    AgeRangePlan,
    KeywordsPlan,
    SalaryPlan,
    SearchPlan,
)

logger = logging.getLogger(__name__)

# Normalization taxonomies
CANONICAL_SKILLS: Dict[str, str] = {
    "ml": "Machine Learning",
    "machine learning": "Machine Learning",
    "ai": "Artificial Intelligence",
    "artificial intelligence": "Artificial Intelligence",
    "nlp": "NLP",
    "natural language processing": "NLP",
    "llm": "LLM",
    "large language models": "LLM",
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
    "node": "Node.js",
    "nodejs": "Node.js",
    "sql": "SQL",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "pyspark": "PySpark",
    "spark": "Apache Spark",
    "kafka": "Kafka",
    "airflow": "Apache Airflow",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "aws": "AWS",
    "azure": "Azure",
    "gcp": "GCP",
    "golang": "Golang",
    "go": "Golang",
    "java": "Java",
    # SAP Modules & Ecosystem
    "sap": "SAP",
    "sap bi": "SAP BI",
    "sap bw": "SAP BW",
    "sap business warehouse": "SAP Business Warehouse",
    "sap business intelligence": "SAP BI",
    "sap hana": "SAP HANA",
    "hana": "SAP HANA",
    "s/4hana": "SAP S/4HANA",
    "s4hana": "SAP S/4HANA",
    "sap erp": "SAP ERP",
    "sap fico": "SAP FICO",
    "fico": "SAP FICO",
    "sap mm": "SAP MM",
    "sap sd": "SAP SD",
    "sap abap": "SAP ABAP",
    "abap": "SAP ABAP",
    "sap basis": "SAP Basis",
    "sap mdg": "SAP MDG",
    "sap master data governance": "SAP MDG",
    "sap ariba": "SAP Ariba",
    "sap successfactors": "SAP SuccessFactors",
    "sap crm": "SAP CRM",
    "sap scm": "SAP SCM",
    "sap pp": "SAP PP",
    "sap pm": "SAP PM",
    # DevOps & Infrastructure
    "terraform": "Terraform",
    "ansible": "Ansible",
    "jenkins": "Jenkins",
    "ci/cd": "CI/CD",
    "linux": "Linux",
    # Data & Analytics
    "power bi": "Power BI",
    "tableau": "Tableau",
    "snowflake": "Snowflake",
    "databricks": "Databricks",
    "bigquery": "BigQuery",
    # Frontend & Fullstack
    "angular": "Angular",
    "vue": "Vue.js",
    "vuejs": "Vue.js",
    "nextjs": "Next.js",
    "next.js": "Next.js",
}

LOCATION_ALIASES: Dict[str, str] = {
    "hyd": "Hyderabad",
    "hyderabad": "Hyderabad",
    "bangalore": "Bengaluru",
    "bengaluru": "Bengaluru",
    "blr": "Bengaluru",
    "pune": "Pune",
    "delhi": "Delhi",
    "delhi ncr": "Delhi NCR",
    "ncr": "Delhi NCR",
    "noida": "Noida",
    "gurgaon": "Gurgaon",
    "gurugram": "Gurgaon",
    "chennai": "Chennai",
    "mumbai": "Mumbai",
    "kolkata": "Kolkata",
    "ahmedabad": "Ahmedabad",
    "kochi": "Kochi",
    "chandigarh": "Chandigarh",
    "jaipur": "Jaipur",
    "indore": "Indore",
    "coimbatore": "Coimbatore",
}

NOTICE_PERIOD_MAP: Dict[str, str] = {
    "immediate": "0-15 days",
    "immediate joiner": "0-15 days",
    "immediately": "0-15 days",
    "15 days": "0-15 days",
    "0-15 days": "0-15 days",
    "1 month": "1 month",
    "one month": "1 month",
    "30 days": "1 month",
    "2 months": "2 months",
    "two months": "2 months",
    "60 days": "2 months",
    "3 months": "3 months",
    "three months": "3 months",
    "90 days": "3 months",
    "serving notice": "Currently serving notice period",
    "serving notice period": "Currently serving notice period",
}


def load_resdex_schema() -> Dict[str, Any]:
    """Loads semantic Resdex schema from resdex_schema.json."""
    schema_path = os.path.join(
        os.path.dirname(__file__), "..", "schemas", "resdex_schema.json"
    )
    if os.path.exists(schema_path):
        with open(schema_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


class RequirementAgent:
    """
    Schema-driven AI Requirement Agent.
    Transforms natural-language recruitment requirements into structured Resdex SearchPlans.
    Never invents requirements; leaves unmentioned fields as None.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
    ):
        self.groq_api_key = api_key or settings.GROQ_API_KEY
        self.gemini_api_key = settings.GEMINI_API_KEY

        self.model = model or settings.GROQ_MODEL
        self.schema = schema or load_resdex_schema()

    def generate_search_plan(self, requirement: str) -> SearchPlan:
        """
        Main entrypoint: parses requirement into validated SearchPlan.
        Acts as an expert HR Recruiter using an LLM model (Groq or Gemini) if an API key is available,
        falling back to deterministic HR extraction rules.
        """
        if not requirement or not requirement.strip():
            return SearchPlan(confidence=0.0, uncertain_fields=["requirement_empty"])

        cleaned = requirement.strip()

        # Step 1: Attempt LLM generation as a Senior HR Recruiter (Groq or Gemini)
        llm_plan = self._call_llm_as_hr(cleaned)
        if llm_plan:
            return self._post_process_plan(llm_plan, cleaned)

        # Step 2: Deterministic Rule-Based extraction (acting as HR)
        rule_plan = self._rule_based_extraction(cleaned)
        return self._post_process_plan(rule_plan, cleaned)

    def _call_llm_as_hr(self, requirement: str) -> Optional[SearchPlan]:
        """
        Calls Groq or Google Gemini as a Senior Technical HR Recruiter.
        Translates raw hiring descriptions into targeted Resdex candidate search plans.
        """
        # Determine provider and endpoint (Groq or Gemini ONLY)
        api_url = None
        api_key = None
        model = self.model

        if self.groq_api_key:
            api_url = settings.GROQ_API_URL
            api_key = self.groq_api_key
            model = settings.GROQ_MODEL or "openai/gpt-oss-20b"
        elif self.gemini_api_key:
            api_url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
            api_key = self.gemini_api_key
            model = getattr(settings, "GEMINI_MODEL", "gemini-1.5-flash")
        else:
            logger.info("No LLM API key detected (Groq/Gemini). Using HR Rule-Based Engine.")
            return None

        # Compact system prompt — avoids exceeding model context/output limits
        system_prompt = """You are a Senior HR Recruiter filling a candidate search form.
Read the job description and return ONLY a JSON object with these exact fields:

{
  "keywords": {"required": ["skill1", "skill2"], "preferred": ["skill3"], "excluded": [], "mandatory": true, "search_scope": "Entire resume"},
  "min_experience": 5,
  "max_experience": 10,
  "current_location": ["City"],
  "include_relocation": false,
  "salary": {"currency": "INR", "min": null, "max": null},
  "department_role": ["Role Name"],
  "designation": ["Job Title"],
  "notice_period": ["0-15 days", "1 month"],
  "gender": null,
  "job_type": null,
  "employment_type": null,
  "candidate_display": "All candidates",
  "verified_mobile": true,
  "verified_email": true,
  "attached_resume": true,
  "active_in": "15 days",
  "confidence": 0.95,
  "uncertain_fields": []
}

Rules:
- keywords.required = must-have technical skills and tools explicitly stated in the JD
- keywords.preferred = nice-to-have or secondary skills mentioned in the JD
- notice_period must be a flat list of strings like ["0-15 days"], never a dict
- Experience: infer from role level if not stated (Lead=6-12, Senior=4-8, Mid=2-5, Junior=0-2)
- Always set verified_mobile=true, verified_email=true, attached_resume=true, active_in="15 days"
- Return ONLY raw JSON. No markdown, no explanation."""

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"Job Description:\n\n{requirement}\n\n"
                        "Return ONLY the JSON object."
                    ),
                },
            ],
            "temperature": 0.1,
            "max_tokens": 1200,
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(api_url, headers=headers, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    content = data["choices"][0]["message"]["content"].strip()

                    # Strip markdown code fences if present
                    if content.startswith("```"):
                        content = re.sub(r"^```(?:json)?", "", content)
                        content = re.sub(r"```$", "", content).strip()

                    # Attempt to repair truncated/unterminated JSON
                    content = self._repair_json(content)

                    parsed = json.loads(content)

                    # Sanitize common LLM output mistakes before Pydantic validation
                    parsed = self._sanitize_llm_output(parsed)

                    logger.info(f"LLM HR Agent successfully parsed SearchPlan using {model}")
                    return SearchPlan(**parsed)
                else:
                    logger.warning(f"LLM API ({model}) returned {response.status_code}: {response.text[:300]}")
        except Exception as exc:
            logger.warning(f"LLM HR parsing failed: {exc}")

        return None

    def _repair_json(self, content: str) -> str:
        """Attempt to repair truncated/unterminated JSON responses from LLM."""
        content = content.strip()
        if not content:
            return "{}"

        # Find the last valid JSON object boundary
        # Try to find and close an unterminated JSON object
        try:
            json.loads(content)
            return content  # Already valid
        except json.JSONDecodeError:
            pass

        # Count unmatched braces/brackets to auto-close
        stack = []
        in_string = False
        escape_next = False
        last_good_pos = 0

        for i, ch in enumerate(content):
            if escape_next:
                escape_next = False
                continue
            if ch == "\\" and in_string:
                escape_next = True
                continue
            if ch == '"' and not escape_next:
                in_string = not in_string
                if not in_string:
                    last_good_pos = i
                continue
            if in_string:
                continue
            if ch in "{[":
                stack.append(ch)
            elif ch in "}]":
                if stack:
                    stack.pop()
                last_good_pos = i

        # Close any open strings first, then brackets/braces
        closing = ""
        if in_string:
            closing += '"'
        for opener in reversed(stack):
            closing += "}" if opener == "{" else "]"

        repaired = content + closing
        try:
            json.loads(repaired)
            logger.info("JSON auto-repaired (closed unterminated structure)")
            return repaired
        except json.JSONDecodeError:
            # Last resort: truncate to last known good position
            truncated = content[: last_good_pos + 1]
            for opener in reversed(stack):
                truncated += "}" if opener == "{" else "]"
            try:
                json.loads(truncated)
                logger.info("JSON truncated and repaired")
                return truncated
            except Exception:
                return "{}"

    def _sanitize_llm_output(self, parsed: dict) -> dict:
        """
        Fixes common LLM output mistakes before Pydantic validation:
        - notice_period as dict instead of list
        - current_location as dict instead of list
        - department_role/designation/industry wrapped in a dict
        - numeric strings for experience
        """
        # Fix notice_period: must be List[str]
        np = parsed.get("notice_period")
        if isinstance(np, dict):
            # e.g. {"notice_period": ["Any"]} or {"0-15 days": true}
            vals = list(np.values())
            if vals and isinstance(vals[0], list):
                parsed["notice_period"] = vals[0]
            else:
                parsed["notice_period"] = [k for k in np.keys() if k != "notice_period"]
        elif isinstance(np, str):
            parsed["notice_period"] = [np] if np else None

        # Fix current_location: must be List[str]
        loc = parsed.get("current_location")
        if isinstance(loc, str):
            parsed["current_location"] = [loc] if loc else None
        elif isinstance(loc, dict):
            parsed["current_location"] = list(loc.values())

        # Fix list fields that sometimes come as strings
        for list_field in ("department_role", "designation", "industry", "company", "exclude_company", "work_permit"):
            val = parsed.get(list_field)
            if isinstance(val, str):
                parsed[list_field] = [val] if val else None
            elif isinstance(val, dict):
                parsed[list_field] = list(val.values()) or None

        # Fix keywords: sometimes LLM returns keywords as a flat list instead of object
        kw = parsed.get("keywords")
        if isinstance(kw, list):
            parsed["keywords"] = {"required": kw, "preferred": [], "excluded": [], "mandatory": True, "search_scope": "Entire resume"}

        # Ensure experience is numeric
        for exp_field in ("min_experience", "max_experience"):
            val = parsed.get(exp_field)
            if isinstance(val, str):
                try:
                    parsed[exp_field] = float(val)
                except (ValueError, TypeError):
                    parsed[exp_field] = None

        # Ensure confidence is a float 0-1
        conf = parsed.get("confidence", 1.0)
        if isinstance(conf, str):
            try:
                parsed["confidence"] = float(conf)
            except (ValueError, TypeError):
                parsed["confidence"] = 0.9
        if parsed.get("confidence", 1.0) > 1.0:
            parsed["confidence"] = parsed["confidence"] / 100.0

        return parsed



    def _rule_based_extraction(self, text: str) -> SearchPlan:
        """Deterministic rule-based extraction matching all 8 Agent Rules."""
        lower = text.lower()

        # 1. Skills Extraction (Required vs Preferred)
        req_skills, pref_skills = self._extract_skills_rule(text)
        keywords_plan = None
        if req_skills or pref_skills:
            keywords_plan = KeywordsPlan(
                required=req_skills,
                preferred=pref_skills,
                excluded=[],
                mandatory=True,
                search_scope="Entire resume",
            )

        # 2. Experience Extraction
        min_exp, max_exp = self._extract_experience_rule(text)

        # 3. Location Extraction
        locations, include_relo = self._extract_locations_rule(text)

        # 4. Salary Extraction
        salary_plan = self._extract_salary_rule(text)

        # 5. Department/Role & Designation
        roles, designations = self._extract_roles_rule(text)

        # 6. Notice Period Extraction
        notice_periods = self._extract_notice_period_rule(text)

        # 7. Diversity Hiring (only if explicitly stated)
        gender = None
        if re.search(r"\bfemale candidates?\b|\bwomen candidates?\b", lower):
            gender = "Female candidates"
        elif re.search(r"\bmale candidates?\b", lower):
            gender = "Male candidates"

        career_break = None
        if "women returning to work" in lower or "career break" in lower:
            career_break = "Women returning to work"

        differently_abled = None
        if "differently abled" in lower or "pwd" in lower or "disability" in lower:
            differently_abled = "Any"

        defence_bg = None
        if "defence" in lower or "military" in lower or "army" in lower:
            defence_bg = "Any"

        # 8. Additional Details
        job_type = None
        if "permanent" in lower:
            job_type = "Permanent"
        elif "contract" in lower or "temporary" in lower:
            job_type = "Temporary/Contract job"

        emp_type = None
        if "full time" in lower or "full-time" in lower:
            emp_type = "Full time"
        elif "part time" in lower or "part-time" in lower:
            emp_type = "Part time"

        return SearchPlan(
            keywords=keywords_plan,
            min_experience=min_exp,
            max_experience=max_exp,
            current_location=locations or None,
            include_relocation=include_relo,
            salary=salary_plan,
            department_role=roles or None,
            designation=designations or None,
            notice_period=notice_periods or None,
            gender=gender,
            career_break=career_break,
            differently_abled=differently_abled,
            defence_background=defence_bg,
            job_type=job_type,
            employment_type=emp_type,
            candidate_display="All candidates",
            verified_mobile=True,
            verified_email=True,
            attached_resume=True,
            active_in="15 days",
            confidence=0.95,
            uncertain_fields=[],
        )

    def _extract_skills_rule(self, text: str) -> Tuple[List[str], List[str]]:
        """
        Separates required from preferred skills using:
        1. Section parsing (e.g. 'Must Have', 'Required Skills', 'Technical Skills', 'Nice to have', 'Preferred')
        2. Bullet point parsing
        3. Canonical skill taxonomy matching
        """
        required_skills: List[str] = []
        preferred_skills: List[str] = []

        # 1. Section Header & Bullet Extraction
        raw_lines = [l.strip() for l in text.splitlines() if l.strip()]
        current_section = 0  # 0 = neutral/other, 1 = required, 2 = preferred

        req_header_re = re.compile(
            r"^(?:must\s*have|required\s*skills?|mandatory\s*skills?|key\s*skills?|technical\s*skills?|requirements?|core\s*skills?|skills\s*required)[:\s]*$",
            re.IGNORECASE,
        )
        pref_header_re = re.compile(
            r"^(?:nice\s*to\s*have|preferred\s*skills?|good\s*to\s*have|optional\s*skills?|preferred)[:\s]*$",
            re.IGNORECASE,
        )
        other_header_re = re.compile(
            r"^(?:job\s*description|responsibilities|duties|roles?|about|benefits|qualifications|education|about\s*us)[:\s]*$",
            re.IGNORECASE,
        )

        for line in raw_lines:
            if req_header_re.match(line):
                current_section = 1
                continue
            elif pref_header_re.match(line):
                current_section = 2
                continue
            elif other_header_re.match(line):
                current_section = 0
                continue

            if current_section in (1, 2):
                # Clean leading bullets, dashes, numbers
                cleaned = re.sub(r"^[•\*\-\–\—\d+\.\)\s]+", "", line).strip()
                # Clean trailing punctuation
                cleaned = re.sub(r"[;,.]+$", "", cleaned).strip()

                # Filter out long full sentences / instructions
                if (
                    cleaned
                    and len(cleaned) <= 65
                    and not cleaned.lower().startswith(
                        ("lead ", "collaborate ", "responsible ", "must have", "provide ", "conduct ", "troubleshoot ")
                    )
                ):
                    target_list = required_skills if current_section == 1 else preferred_skills
                    if cleaned not in target_list:
                        target_list.append(cleaned)

        # 2. Canonical taxonomy extraction for mentioned skills
        lower = text.lower()
        pref_match = re.search(
            r"(?:prefer|preferred|nice to have|good to have|optional)[:\s]+([^.\n]+)",
            lower,
        )
        pref_text = pref_match.group(1) if pref_match else ""

        for alias, canonical in sorted(
            CANONICAL_SKILLS.items(), key=lambda x: len(x[0]), reverse=True
        ):
            if alias == "ai" and ("ai/ml" in lower or "ai-ml" in lower):
                continue
            pattern = rf"\b{re.escape(alias)}\b"
            if re.search(pattern, lower):
                if pref_text and re.search(pattern, pref_text):
                    if canonical not in preferred_skills:
                        preferred_skills.append(canonical)
                else:
                    if canonical not in required_skills:
                        required_skills.append(canonical)

        return required_skills, preferred_skills

    def _extract_experience_rule(
        self, text: str
    ) -> Tuple[Optional[float], Optional[float]]:
        """Extracts experience bounds (Rule 4)."""
        lower = text.lower()

        # Fresher check
        if "fresher" in lower or "0 years" in lower or "entry level" in lower:
            return 0.0, 1.0

        # "2 to 5 years" or "2-5 years" or "2 - 5 yrs"
        range_match = re.search(
            r"(\d+(?:\.\d+)?)\s*(?:to|-)\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?)", lower
        )
        if range_match:
            return float(range_match.group(1)), float(range_match.group(2))

        # "at least 3 years" or "min 3 years" or "3+ years"
        min_match = re.search(
            r"(?:at least|minimum|min|above)\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?)",
            lower,
        )
        if min_match:
            return float(min_match.group(1)), None

        plus_match = re.search(r"(\d+(?:\.\d+)?)\s*\+\s*(?:years?|yrs?)", lower)
        if plus_match:
            return float(plus_match.group(1)), None

        # "up to 5 years" or "maximum 5 years" or "max 5 yrs"
        max_match = re.search(
            r"(?:up to|maximum|max|under|below)\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?)",
            lower,
        )
        if max_match:
            return None, float(max_match.group(1))

        # Single number "3 years experience"
        single_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:years?|yrs?)", lower)
        if single_match:
            val = float(single_match.group(1))
            return val, None

        # HR Recruiter Seniority Inference (when explicit experience numbers are omitted)
        if re.search(r"\b(?:lead|principal|architect|director|head|vp)\b", lower):
            return 6.0, 12.0
        if re.search(r"\b(?:senior|sr\.?|specialist|expert)\b", lower):
            return 4.0, 8.0
        if re.search(r"\b(?:mid[- ]level|associate|consultant)\b", lower):
            return 2.0, 5.0
        if re.search(r"\b(?:junior|jr\.?|trainee|entry[- ]level)\b", lower):
            return 0.0, 2.0

        return None, None

    def _extract_locations_rule(
        self, text: str
    ) -> Tuple[List[str], Optional[bool]]:
        """Extracts location cities and relocation preferences."""
        lower = text.lower()
        locations: List[str] = []

        for alias, canonical in LOCATION_ALIASES.items():
            pattern = rf"\b{re.escape(alias)}\b"
            if re.search(pattern, lower):
                if canonical not in locations:
                    locations.append(canonical)

        include_relocation = None
        if "relocate" in lower or "relocation" in lower:
            include_relocation = True

        return locations, include_relocation

    def _extract_salary_rule(self, text: str) -> Optional[SalaryPlan]:
        """Extracts salary constraints (Rule 5)."""
        lower = text.lower()

        # "8 to 15 LPA" or "8-15 LPA" or "8-15 lakhs"
        range_match = re.search(
            r"(\d+(?:\.\d+)?)\s*(?:to|-)\s*(\d+(?:\.\d+)?)\s*(?:lpa|lakhs?|lac|l)",
            lower,
        )
        if range_match:
            return SalaryPlan(
                currency="INR",
                min=float(range_match.group(1)),
                max=float(range_match.group(2)),
            )

        # "below 12 LPA" or "up to 12 LPA" or "maximum 10 lakhs"
        max_match = re.search(
            r"(?:below|up to|max|maximum|under)\s*(\d+(?:\.\d+)?)\s*(?:lpa|lakhs?|lac|l)",
            lower,
        )
        if max_match:
            return SalaryPlan(
                currency="INR",
                min=None,
                max=float(max_match.group(1)),
            )

        # "min 8 LPA" or "at least 8 LPA"
        min_match = re.search(
            r"(?:above|min|minimum|at least)\s*(\d+(?:\.\d+)?)\s*(?:lpa|lakhs?|lac|l)",
            lower,
        )
        if min_match:
            return SalaryPlan(
                currency="INR",
                min=float(min_match.group(1)),
                max=None,
            )

        return None

    def _extract_notice_period_rule(self, text: str) -> Optional[List[str]]:
        """Extracts notice period constraints (Rule 6)."""
        lower = text.lower()
        matched: List[str] = []

        for phrase, option in NOTICE_PERIOD_MAP.items():
            if phrase in lower:
                if option not in matched:
                    matched.append(option)

        return matched if matched else None

    def _extract_roles_rule(
        self, text: str
    ) -> Tuple[List[str], List[str]]:
        """Extracts department roles and designations."""
        lower = text.lower()
        roles: List[str] = []
        designations: List[str] = []

        if "ai/ml" in lower or "ai-ml" in lower or ("ai" in lower and "ml" in lower):
            roles.append("AI/ML Engineer")
            designations.extend(["AI Engineer", "Machine Learning Engineer", "ML Engineer"])
        elif "data engineer" in lower:
            roles.append("Data Engineer")
            designations.extend(["Data Engineer", "Senior Data Engineer", "Big Data Engineer"])
        elif "react" in lower or "frontend" in lower:
            roles.append("Frontend Developer")
            designations.extend(["Frontend Developer", "React Developer", "UI Developer"])
        elif "python" in lower:
            roles.append("Python Developer")
            designations.extend(["Python Developer", "Python Backend Engineer"])
        elif "sap" in lower:
            roles.append("SAP Consultant")
            if "lead" in lower:
                designations.extend(["Lead SAP Consultant", "SAP Implementation Lead", "SAP Project Lead"])
            else:
                designations.extend(["SAP Consultant", "SAP Specialist", "Senior SAP Consultant"])

        return roles, designations

    def _post_process_plan(self, plan: SearchPlan, raw_text: str) -> SearchPlan:
        """Enforces normalization rules and sets defaults."""
        # Ensure notice period normalization
        if plan.notice_period:
            normalized_np = []
            for np in plan.notice_period:
                if np in NOTICE_PERIOD_MAP.values():
                    normalized_np.append(np)
                elif np.lower() in NOTICE_PERIOD_MAP:
                    normalized_np.append(NOTICE_PERIOD_MAP[np.lower()])
            plan.notice_period = list(dict.fromkeys(normalized_np)) or None

        # Ensure default search periods and additional details
        if not plan.active_in:
            plan.active_in = "15 days"
        if not plan.candidate_display:
            plan.candidate_display = "All candidates"
        if plan.verified_mobile is None:
            plan.verified_mobile = True
        if plan.verified_email is None:
            plan.verified_email = True
        if plan.attached_resume is None:
            plan.attached_resume = True
        if plan.keywords and plan.keywords.required:
            plan.keywords.mandatory = True

        return plan
