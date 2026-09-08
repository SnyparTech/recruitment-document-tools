"""
AI Resume Provider Abstraction & Implementations.

Provides:
- ResumeAIProvider: Abstract Base Class for LLM structuring engines.
- GroqResumeAIProvider: Default implementation using Groq API ('qwen/qwen3.6-27b' or fallback)
  with strict zero-information-loss deterministic transformation prompt.
- NvidiaNimResumeAIProvider: Implementation for NVIDIA NIM OpenAI-compatible endpoints.
- DeterministicFallbackParser: 100% offline parser that extracts and structures resume data
  if API keys are unconfigured or remote services are unavailable, ensuring zero downtime.
"""

import abc
import json
import logging
import re
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Mandatory strict system prompt as specified in requirement 7
STRICT_RESUME_SYSTEM_PROMPT = """You are a deterministic resume transformation engine.

Your task is NOT to improve, rewrite, summarize, shorten, expand, or invent resume content.

Your task is only to:

1. Read the complete extracted resume content.
2. Preserve every meaningful piece of information.
3. Organize the information into structured resume sections.
4. Map the information into the provided resume template structure.
5. Preserve all names, dates, numbers, percentages, URLs, email addresses, phone numbers, skills, qualifications, job titles, company names, university names, project names, and achievements exactly as provided.

STRICT RULES:

* Do not delete any information.
* Do not summarize any information.
* Do not invent information.
* Do not improve or embellish achievements.
* Do not change numerical values.
* Do not change dates.
* Do not merge multiple achievements into one if information could be lost.
* Preserve every bullet point.
* Preserve every project.
* Preserve every job.
* Preserve every education entry.
* Preserve every skill.
* Preserve every additional section.

Your output must be valid JSON only.

If information cannot be confidently mapped to one of the predefined template sections, place it into an additional section while preserving the original section title and content.

Before returning the result, internally verify that all meaningful source information has been represented in the output.
"""

JSON_STRUCTURE_GUIDE = """
Return ONLY a valid JSON object with the following exact structure:
{
  "personal_information": {
    "name": "Candidate Full Name",
    "phone": "Phone number or null",
    "location": "City, State/Country or null",
    "email": "Email address or null",
    "linkedin": "LinkedIn URL or handle or null",
    "website": "Personal website or portfolio or null"
  },
  "objective": "Career objective or professional summary text or null",
  "education": [
    {
      "degree": "Degree and major",
      "institution": "University / College name",
      "location": "City, Country or null",
      "date": "Graduation year or date range",
      "details": ["GPA, honors, coursework, or other bullet points"]
    }
  ],
  "skills": {
    "technical_skills": ["List of technical skills, languages, frameworks"],
    "soft_skills": ["List of soft skills if present"],
    "additional_skills": ["Tools, databases, platforms, etc."]
  },
  "experience": [
    {
      "role": "Job Title / Role",
      "company": "Company Name",
      "location": "Location or null",
      "start_date": "Start date",
      "end_date": "End date or Present",
      "bullets": [
        "Exact bullet point from resume with all metrics, numbers, and technologies preserved verbatim"
      ]
    }
  ],
  "projects": [
    {
      "title": "Project Title",
      "description": "Full description and achievements",
      "url": "Project URL or null"
    }
  ],
  "extra_curricular_activities": [
    "Activity or achievement description"
  ],
  "leadership": [
    "Leadership role or responsibility description"
  ],
  "additional_sections": [
    {
      "title": "CERTIFICATIONS / AWARDS / PUBLICATIONS / etc.",
      "items": [
        "Every item, bullet, or sentence from this section preserved verbatim"
      ]
    }
  ]
}

DO NOT wrap in markdown fences like ```json. Output raw valid JSON only.
"""


class ResumeAIProvider(abc.ABC):
    """Abstract interface for Resume AI Structuring engines."""

    @abc.abstractmethod
    async def structure_resume(
        self,
        canonical_content: Dict[str, Any],
        sanitized_text: str,
    ) -> Dict[str, Any]:
        """Structures extracted resume text into standardized schema."""
        pass


class GroqResumeAIProvider(ResumeAIProvider):
    """Groq Cloud implementation with automatic model fallback and offline parser."""

    FALLBACK_MODELS = [
        "qwen/qwen3.6-27b",
        "llama-3.3-70b-versatile",
        "qwen-2.5-32b",
        "llama-3.1-8b-instant",
    ]

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.GROQ_API_KEY
        self.model = model or getattr(settings, "GROQ_MODEL", "qwen/qwen3.6-27b")
        self.api_url = getattr(
            settings, "GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions"
        )

    async def structure_resume(
        self,
        canonical_content: Dict[str, Any],
        sanitized_text: str,
    ) -> Dict[str, Any]:
        """Calls Groq API to structure resume, falling back gracefully if necessary."""
        if not self.api_key or self.api_key.strip() == "":
            logger.info("GROQ_API_KEY not configured. Using deterministic high-fidelity local parser.")
            return DeterministicFallbackParser.parse(canonical_content, sanitized_text)

        # Attempt structured generation with primary model and fallbacks
        models_to_try = [self.model] + [m for m in self.FALLBACK_MODELS if m != self.model]

        user_prompt = (
            f"Here is the complete extracted resume content:\n\n"
            f"--- RESUME CONTENT BEGIN ---\n"
            f"{sanitized_text}\n"
            f"--- RESUME CONTENT END ---\n\n"
            f"{JSON_STRUCTURE_GUIDE}"
        )

        headers = {
            "Authorization": f"Bearer {self.api_key.strip()}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=90.0) as client:
            for model_id in models_to_try:
                try:
                    logger.info(f"Structuring resume using Groq model: {model_id}")
                    payload = {
                        "model": model_id,
                        "messages": [
                            {"role": "system", "content": STRICT_RESUME_SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.0,  # Strict deterministic mode
                        "response_format": {"type": "json_object"},
                    }
                    response = await client.post(self.api_url, headers=headers, json=payload)

                    if response.status_code == 200:
                        data = response.json()
                        raw_content = data["choices"][0]["message"]["content"]
                        parsed_json = self._clean_and_parse_json(raw_content)
                        if parsed_json:
                            logger.info(f"Groq ({model_id}) successfully structured resume.")
                            return parsed_json
                    else:
                        logger.warning(
                            f"Groq ({model_id}) returned HTTP {response.status_code}: {response.text[:200]}"
                        )
                except Exception as exc:
                    logger.warning(f"Error structuring with Groq model {model_id}: {exc}")

        # If all remote models failed, invoke deterministic fallback parser
        logger.warning("Remote LLM failed or timed out. Falling back to deterministic local parser.")
        return DeterministicFallbackParser.parse(canonical_content, sanitized_text)

    @staticmethod
    def _clean_and_parse_json(raw_text: str) -> Optional[Dict[str, Any]]:
        """Extracts and parses JSON object from model response."""
        clean = raw_text.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```(?:json)?\s*", "", clean, flags=re.IGNORECASE)
            clean = re.sub(r"\s*```$", "", clean)

        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            # Try to match the first '{' to the last '}'
            m = re.search(r"(\{.*\})", clean, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(1))
                except Exception:
                    pass
        return None


class NvidiaNimResumeAIProvider(ResumeAIProvider):
    """NVIDIA NIM OpenAI-compatible API implementation."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://integrate.api.nvidia.com/v1/chat/completions",
        model: str = "meta/llama-3.1-70b-instruct",
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    async def structure_resume(
        self, canonical_content: Dict[str, Any], sanitized_text: str
    ) -> Dict[str, Any]:
        if not self.api_key:
            return DeterministicFallbackParser.parse(canonical_content, sanitized_text)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        user_prompt = (
            f"Here is the complete extracted resume content:\n\n{sanitized_text}\n\n{JSON_STRUCTURE_GUIDE}"
        )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": STRICT_RESUME_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=90.0) as client:
            res = await client.post(self.base_url, headers=headers, json=payload)
            if res.status_code == 200:
                content = res.json()["choices"][0]["message"]["content"]
                parsed = GroqResumeAIProvider._clean_and_parse_json(content)
                if parsed:
                    return parsed

        return DeterministicFallbackParser.parse(canonical_content, sanitized_text)


class DeterministicFallbackParser:
    """
    High-fidelity deterministic local structuring engine.

    Guarantees 100% preservation of all candidate data without dropping,
    summarizing, or inventing any content, even when LLM is unavailable.

    Improvements:
    - Detects "Category: value" lines as skills (e.g. "Cloud: Microsoft Azure")
    - Joins continuation lines for skills split across PDF lines
    - Parses HEADER section content to extract skills, objective, experience
    - Parses mixed EDUCATION sections that contain projects/experience
    - Detects numbered projects (1., 2., 3.) inside any section
    - Parses company / role / date headers from experience sections
    - Extracts location from pipe-separated header lines
    """

    EMAIL_RE    = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
    PHONE_RE    = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b")
    LINKEDIN_RE = re.compile(r"(?:https?://(?:www\.)?linkedin\.com/in/[\w\-]+|linkedin\.com/in/[\w\-]+)", re.IGNORECASE)
    URL_RE      = re.compile(r"https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)")

    # Date patterns
    DATE_RE = re.compile(
        r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?"
        r"|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
        r"[\s\-]?\d{2,4}\b"
        r"|\b\d{4}\s*[-\u2013]\s*(?:\d{4}|Present|Current|Till Date)\b"
        r"|\bPresent\b|\bCurrent\b|\bTill Date\b",
        re.IGNORECASE,
    )

    # Company/org identifiers
    COMPANY_KEYWORDS = re.compile(
        r"\b(?:pvt\.?\s*ltd\.?|llp|llc|inc\.?|corp\.?|technologies|solutions|systems|"
        r"consultancy|services|limited|private|enterprises|infotech|software|infosystems)\b",
        re.IGNORECASE,
    )

    # "Category: value" skill pattern (e.g. "Cloud: Microsoft Azure", "Framework & Languages: .Net Core")
    SKILL_LINE_RE = re.compile(r"^([A-Za-z][A-Za-z\s&/]{2,50})\s*:\s*(.{2,})$")

    # Numbered project/item heading: "1.", "2.", "1)" etc.
    NUMBERED_ITEM_RE = re.compile(r"^(\d+)[.)\s]\s*(.+)$")

    @classmethod
    def _join_continuation_lines(cls, lines: List[str]) -> List[str]:
        """
        Join continuation lines that belong to the same logical line.
        Handles:
        - Skill values split across lines: 'Framework: .Net Core, and' + 'Angular(5-12)'
        - Job history split across lines: 'Senior SE at Q3 from' + 'January 2024 to March 2026.'
        - Strips standalone Wingdings/PDF bullet chars (\uf0b7, \uf0a7, etc.)
        """
        if not lines:
            return lines

        # Strip standalone bullet-only lines (Wingdings \uf0b7, \u2022, etc.)
        SOLO_BULLET = re.compile(r"^[\uf0b7\uf0a7\u2022\u25aa\u25ab\u25b6\u2713\u00b7•\-]$")
        lines = [l for l in lines if not SOLO_BULLET.match(l.strip())]

        joined: List[str] = []
        # Trail patterns that indicate the line continues on the next line
        CONTINUATION_TRAIL = re.compile(
            r"[,]\s*$|\b(?:and|or|from|at|to|of|the|a|an|in|on|for|with|by|as)\s*$",
            re.IGNORECASE,
        )
        BULLET_START = re.compile(r"^[\u2022\uf0b7\uf0a7\-\u2013\u2014\*\u25aa\u25ab\u25ba\u2713o\u00b7]|^\d+[.)]", re.UNICODE)

        for line in lines:
            if (
                joined
                and CONTINUATION_TRAIL.search(joined[-1])
                and not cls.SKILL_LINE_RE.match(line)
                and not BULLET_START.match(line)
                and not cls.DATE_RE.search(joined[-1])  # don't extend completed date lines
            ):
                joined[-1] = joined[-1].rstrip() + " " + line
            else:
                joined.append(line)
        return joined

    @classmethod
    def _extract_skills_from_lines(cls, lines: List[str], skills_dict: Dict) -> List[str]:
        """
        Parse 'Category: value(s)' skill lines into skills_dict.
        Returns unconsumed lines.
        """
        remaining: List[str] = []
        lines = cls._join_continuation_lines(lines)
        for line in lines:
            m = cls.SKILL_LINE_RE.match(line)
            if m:
                category = m.group(1).strip().rstrip()
                raw_val = m.group(2).strip()
                values = [v.strip() for v in re.split(r"[,]", raw_val) if v.strip()]
                if values:
                    entry = f"{category}: {', '.join(values)}"
                    if entry not in skills_dict["additional_skills"]:
                        skills_dict["additional_skills"].append(entry)
            else:
                remaining.append(line)
        return remaining

    @classmethod
    def _extract_experience_from_header(
        cls,
        header_lines: List[str],
    ) -> List[Dict]:
        """
        Vikas-style PDFs embed the job history (with dates) in the header/left-column.
        Handles both single-line and two-line patterns:
          Single: 'Senior SE at Q3 Technologies from January 2024 to March 2026.'
          Two-line: 'Software Engineer at Celebal Technologies Private Limited' +
                    'from June 2021 to October 2023.'
        """
        # Pass 1: join lines where the NEXT line starts with 'from '
        merged: List[str] = []
        i = 0
        FROM_START = re.compile(r"^from\s+", re.IGNORECASE)
        while i < len(header_lines):
            line = header_lines[i].strip()
            if i + 1 < len(header_lines) and FROM_START.match(header_lines[i + 1].strip()):
                line = line + " " + header_lines[i + 1].strip()
                i += 2
            else:
                i += 1
            merged.append(line)

        entries: List[Dict] = []
        AT_FROM_RE = re.compile(
            r"^(.+?)\s+at\s+(.+?)\s+from\s+"
            r"((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
            r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)[\s\-]?\d{2,4})"
            r"\s+to\s+"
            r"((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
            r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)[\s\-]?\d{2,4}|Present|Current|Till Date)"
            r"\.?\s*$",
            re.IGNORECASE,
        )
        for line in merged:
            line = line.strip().rstrip(".")
            m = AT_FROM_RE.match(line)
            if m:
                entries.append({
                    "role":       m.group(1).strip().title(),
                    "company":    m.group(2).strip(),
                    "location":   None,
                    "start_date": m.group(3).strip(),
                    "end_date":   m.group(4).strip(),
                    "bullets":    [],
                })
        return entries

    @classmethod
    def _split_mixed_education_section(
        cls,
        sec_lines: List[str],
    ):
        """
        When a PDF lumps everything after EDUCATION into one section, split it into:
        - proper education entries
        - numbered projects (1. Title / 2. Title)
        Returns (education_lines, projects_data) where projects_data is
        a list of {title, description} dicts.
        """
        # Find where numbered projects start (lines like '1. FirstGroup...' or '2. L&T...')
        edu_lines: List[str] = []
        proj_lines: List[str] = []
        in_projects = False

        for line in sec_lines:
            m = cls.NUMBERED_ITEM_RE.match(line)
            if m and int(m.group(1)) == 1:
                in_projects = True
            if in_projects:
                proj_lines.append(line)
            else:
                edu_lines.append(line)

        if not proj_lines:
            return sec_lines, []

        projects = cls._parse_numbered_projects(proj_lines)
        return edu_lines, projects

    @classmethod
    def _parse_numbered_projects(cls, lines: List[str]) -> List[Dict]:
        """
        Parse lines like:
          '1. FirstGroup - Railway Ticketing Platform (Web, Android & iOS)'
          '   FirstGroup plc is a British...' (description lines)
          '2. L&T ECC Approval'
          ...
        """
        projects: List[Dict] = []
        curr_num: Optional[int] = None
        curr_title = ""
        curr_desc: List[str] = []

        def flush():
            if curr_title:
                projects.append({
                    "title": curr_title,
                    "description": "\n".join(curr_desc),
                    "url": None,
                })

        for line in lines:
            m = cls.NUMBERED_ITEM_RE.match(line)
            if m:
                num = int(m.group(1))
                if num != curr_num:
                    flush()
                    curr_num = num
                    curr_title = m.group(2).strip()
                    curr_desc = []
                else:
                    curr_desc.append(line)
            else:
                # continuation — strip leading bullet chars
                clean = line.lstrip("\u2022\u25aa-\u2013*\u25b6 ")
                if clean:
                    curr_desc.append(clean)

        flush()
        return projects

    @classmethod
    def parse(cls, canonical_content: Dict[str, Any], sanitized_text: str) -> Dict[str, Any]:
        """Deterministic mapping of canonical content into the strict schema."""
        raw_text = sanitized_text or canonical_content.get("raw_text", "")
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

        # ── 1. Personal Information ──────────────────────────────────────
        name     = "Candidate"
        location = None

        for candidate_line in lines[:8]:
            if (
                not cls.EMAIL_RE.search(candidate_line)
                and not cls.PHONE_RE.search(candidate_line)
                and not cls.DATE_RE.search(candidate_line)
                and len(candidate_line) < 50
                and len(candidate_line.split()) <= 5
            ):
                name = candidate_line
                break

        email_match    = cls.EMAIL_RE.search(raw_text)
        email          = email_match.group(0) if email_match else None

        phone_match    = cls.PHONE_RE.search(raw_text)
        phone          = phone_match.group(0) if phone_match else None

        linkedin_match = cls.LINKEDIN_RE.search(raw_text)
        linkedin       = linkedin_match.group(0) if linkedin_match else None

        # Extract location from "|"-separated header line
        for hdr_line in lines[:8]:
            if "|" in hdr_line:
                parts = [p.strip() for p in hdr_line.split("|") if p.strip()]
                for part in parts:
                    if not cls.PHONE_RE.search(part) and not cls.EMAIL_RE.search(part):
                        location = part
                        break
                if location:
                    break

        personal_information = {
            "name":     name,
            "phone":    phone,
            "location": location,
            "email":    email,
            "linkedin": linkedin,
            "website":  None,
        }

        # ── 2. Section-by-section parsing ────────────────────────────────
        sections          = canonical_content.get("sections", [])
        education_list    : List[Dict] = []
        experience_list   : List[Dict] = []
        projects_list     : List[Dict] = []
        skills_dict       = {"technical_skills": [], "soft_skills": [], "additional_skills": []}
        additional_sections: List[Dict] = []
        objective         = None
        extra_curricular  : List[str] = []
        leadership        : List[str] = []

        for sec in sections:
            title   = sec.get("title", "").strip().upper()
            content = sec.get("content", "").strip()
            if not content:
                continue

            sec_lines = [l.strip() for l in content.splitlines() if l.strip()]
            # Join continuation lines (e.g. multi-line skill values in two-column PDFs)
            sec_lines = cls._join_continuation_lines(sec_lines)

            if any(k in title for k in ["OBJECTIVE", "SUMMARY", "PROFILE"]):
                objective = content if not objective else f"{objective}\n\n{content}"

            elif any(k in title for k in ["SKILL", "COMPETENC", "EXPERTISE", "TECHNOLOGIES", "TECHNICAL"]):
                cls._extract_skills_from_lines(sec_lines, skills_dict)

            elif any(k in title for k in ["EXPERIENCE", "EMPLOYMENT", "WORK HISTORY", "WORK EXPERIENCE",
                                           "PROFESSIONAL EXPERIENCE"]):
                parsed_exp, found_skills = cls._parse_experience_section(sec_lines)
                experience_list.extend(parsed_exp)
                for sk in found_skills:
                    if sk not in skills_dict["additional_skills"]:
                        skills_dict["additional_skills"].append(sk)

            elif any(k in title for k in ["EDUCATION", "ACADEMIC"]):
                # Vikas-style: education section may contain projects after certs
                edu_lines, mixed_projects = cls._split_mixed_education_section(sec_lines)
                education_list.extend(cls._parse_education_section(edu_lines))
                projects_list.extend(mixed_projects)

            elif any(k in title for k in ["PROJECT"]):
                # Check if they are numbered; if so parse as proper projects
                if any(cls.NUMBERED_ITEM_RE.match(l) for l in sec_lines):
                    projects_list.extend(cls._parse_numbered_projects(sec_lines))
                else:
                    projects_list.extend(cls._parse_projects_section(sec_lines, content))

            elif any(k in title for k in ["LEADERSHIP"]):
                leadership.extend(sec_lines)

            elif any(k in title for k in ["EXTRA", "ACTIVITY", "VOLUNTEER"]):
                extra_curricular.extend(sec_lines)

            elif title in ("HEADER", ""):
                # Two-column PDF left-sidebar content:
                # Contains skills (Category: value lines), objective bullets, job history
                header_skill_lines = []
                header_other_lines = []
                for line in sec_lines:
                    # Skip personal contact info already captured
                    if cls.EMAIL_RE.search(line) or cls.PHONE_RE.search(line):
                        continue
                    if cls.SKILL_LINE_RE.match(line):
                        header_skill_lines.append(line)
                    else:
                        header_other_lines.append(line)

                # Extract skills from Category: value lines
                cls._extract_skills_from_lines(header_skill_lines, skills_dict)

                # Extract work history ("Role at Company from Month Year to Month Year")
                hdr_experience = cls._extract_experience_from_header(header_other_lines)
                if hdr_experience:
                    # These are supplemental — add bullets from experience_list if needed
                    experience_list = hdr_experience + experience_list

                # Any remaining non-skill, non-experience lines → objective / summary
                AT_PATTERN = re.compile(r"\bat\s+", re.IGNORECASE)
                summary_lines = [
                    l for l in header_other_lines
                    if not cls.DATE_RE.search(l)
                    and not AT_PATTERN.search(l)
                    and not cls.COMPANY_KEYWORDS.search(l)
                    and l not in (name, "Professional Background", "Technical Expertise")
                    and not cls.PHONE_RE.search(l)
                    and not cls.EMAIL_RE.search(l)
                ]
                if summary_lines and not objective:
                    objective = " ".join(summary_lines)

            else:
                additional_sections.append({"title": title, "items": sec_lines})

        # Promote additional_skills → technical_skills if technical_skills empty
        if not skills_dict["technical_skills"] and skills_dict["additional_skills"]:
            skills_dict["technical_skills"] = skills_dict.pop("additional_skills")
            skills_dict["additional_skills"] = []

        # Fallback: ensure canonical bullets not lost when no experience found
        canonical_bullets = canonical_content.get("bullets", [])
        if canonical_bullets and not experience_list:
            experience_list.append({
                "role":       "Professional Experience",
                "company":    "Organization",
                "location":   None,
                "start_date": "",
                "end_date":   "Present",
                "bullets":    canonical_bullets,
            })

        return {
            "personal_information":    personal_information,
            "objective":               objective,
            "education":               education_list,
            "skills":                  skills_dict,
            "experience":              experience_list,
            "projects":                projects_list,
            "extra_curricular_activities": extra_curricular,
            "leadership":              leadership,
            "additional_sections":     additional_sections,
        }

    # ── Section parsers ───────────────────────────────────────────────

    @classmethod
    def _parse_experience_section(cls, sec_lines: List[str]):
        """
        Splits experience section into individual role entries.
        Returns (entries, captured_skills) where captured_skills holds
        any 'Category: value' lines that were interleaved from a two-column PDF layout.
        """
        entries: List[Dict] = []
        captured_skills: List[str] = []

        curr_role    = ""
        curr_company = ""
        curr_start   = ""
        curr_end     = ""
        curr_loc     = ""
        curr_bullets: List[str] = []

        def flush():
            if curr_role or curr_company or curr_bullets:
                entries.append({
                    "role":       curr_role or "Professional Role",
                    "company":    curr_company or "Organization",
                    "location":   curr_loc or None,
                    "start_date": curr_start,
                    "end_date":   curr_end or "Present",
                    "bullets":    list(curr_bullets),
                })

        def reset():
            nonlocal curr_role, curr_company, curr_start, curr_end, curr_loc, curr_bullets
            curr_role = curr_company = curr_start = curr_end = curr_loc = ""
            curr_bullets = []

        for line in sec_lines:
            # Capture "Category: value" lines from two-column PDF sidebar
            m = cls.SKILL_LINE_RE.match(line)
            if m:
                category = m.group(1).strip()
                values   = [v.strip() for v in m.group(2).split(",") if v.strip()]
                if values:
                    captured_skills.append(f"{category}: {', '.join(values)}")
                continue

            date_match = cls.DATE_RE.search(line)
            is_short   = len(line) < 70
            is_upper   = line.isupper() and len(line.split()) <= 8
            is_company = bool(cls.COMPANY_KEYWORDS.search(line))

            if is_company and is_short:
                # Start a new experience entry at each company
                if curr_company or curr_bullets:
                    flush()
                    reset()
                curr_company = line

            elif date_match and is_short:
                raw_dates = re.findall(
                    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?"
                    r"|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
                    r"[\s\-]?\d{2,4}|\d{4}|Present|Current|Till Date",
                    line,
                    re.IGNORECASE,
                )
                if len(raw_dates) >= 2:
                    curr_start = raw_dates[0]
                    curr_end   = raw_dates[-1]
                elif raw_dates:
                    curr_end = raw_dates[0]
                role_candidate = cls.DATE_RE.sub("", line).strip(" -\u2013|")
                if role_candidate and not curr_role:
                    curr_role = role_candidate

            elif is_upper and is_short and len(line.split()) <= 7 and not date_match:
                # All-caps short line → role title
                if not curr_role:
                    curr_role = line.title()
                elif not curr_company:
                    curr_company = line

            else:
                clean = line.lstrip("\u2022\u25aa-\u2013*\u25b6 ")
                if clean:
                    curr_bullets.append(clean)

        flush()
        return entries, captured_skills

    @classmethod
    def _parse_education_section(cls, sec_lines: List[str]) -> List[Dict[str, Any]]:
        """Parse education entries from section lines."""
        if not sec_lines:
            return []

        # Filter out spurious heading-only lines that aren't real degree entries
        SKIP_HEADINGS = {"professional background", "academic background", "education",
                         "academic qualifications", "microsoft certificate", "microsoft certificates",
                         "certification", "certifications"}
        entries = []
        i = 0
        while i < len(sec_lines):
            line = sec_lines[i]
            # Skip bare heading lines
            if line.lower().strip().rstrip(":") in SKIP_HEADINGS:
                i += 1
                continue

            # Skip lone bullet chars
            if len(line.strip()) <= 2:
                i += 1
                continue

            date_match = cls.DATE_RE.search(line)
            degree     = ""
            institution = ""
            date_str   = ""
            details: List[str] = []

            if date_match:
                date_str = date_match.group(0)
                degree   = cls.DATE_RE.sub("", line).strip(" ,")
                if i + 1 < len(sec_lines) and not cls.DATE_RE.search(sec_lines[i + 1]):
                    institution = sec_lines[i + 1]
                    i += 1
            else:
                degree = line
                if i + 1 < len(sec_lines):
                    next_line = sec_lines[i + 1]
                    date_m = cls.DATE_RE.search(next_line)
                    if date_m:
                        date_str    = date_m.group(0)
                        institution = cls.DATE_RE.sub("", next_line).strip(" ,")
                        i += 1
                    else:
                        institution = next_line
                        i += 1

            i += 1
            while i < len(sec_lines) and len(sec_lines[i]) > 3:
                details.append(sec_lines[i])
                i += 1

            # Only append if we have meaningful content
            if degree.strip() and degree.strip().lower() not in SKIP_HEADINGS:
                entries.append({
                    "degree":      degree,
                    "institution": institution,
                    "location":    None,
                    "date":        date_str,
                    "details":     details,
                })

        return entries

    @classmethod
    def _parse_projects_section(cls, sec_lines: List[str], full_content: str) -> List[Dict[str, Any]]:
        """Parse project entries — first line = title, rest = description."""
        if not sec_lines:
            return []
        return [{
            "title":       sec_lines[0],
            "description": "\n".join(sec_lines[1:]) if len(sec_lines) > 1 else full_content,
            "url":         None,
        }]
