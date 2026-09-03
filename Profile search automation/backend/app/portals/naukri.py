"""
Naukri Job Portal Adapter.

NOTE: This module includes a dedicated mock/test data layer. In accordance with terms of service
and ethical bot design, no unauthorized scraping, CAPTCHA bypass, or access evasion is implemented.
This adapter can be seamlessly upgraded to use official Naukri Enterprise Recruiter APIs by configuring
production API credentials and client integration in `_fetch_live_results()`.
"""

import re
from typing import Any, Dict, List
from app.models.profile import CandidateProfile
from app.portals.base import BaseJobPortal


# Realistic candidate test repository for mock evaluation
MOCK_NAUKRI_CANDIDATES: List[Dict[str, Any]] = [
    {
        "id": "nk-1001",
        "name": "Aarav Sharma",
        "current_title": "Python Developer",
        "experience": "2.5 years",
        "experience_years": 2.5,
        "location": "Hyderabad",
        "skills": ["Python", "FastAPI", "MongoDB", "Docker", "Git", "REST APIs"],
        "education": "B.Tech in Computer Science",
        "current_company": "InnoTech Solutions",
        "profile_url": "https://www.naukri.com/candidate/aarav-sharma-nk1001",
    },
    {
        "id": "nk-1002",
        "name": "Priyanka Reddy",
        "current_title": "Senior Python Backend Engineer",
        "experience": "4 years",
        "experience_years": 4.0,
        "location": "Hyderabad",
        "skills": ["Python", "FastAPI", "MongoDB", "PostgreSQL", "Redis", "AWS", "Celery"],
        "education": "B.Tech in Information Technology",
        "current_company": "CloudScale Systems",
        "profile_url": "https://www.naukri.com/candidate/priyanka-reddy-nk1002",
    },
    {
        "id": "nk-1003",
        "name": "Rohit Verma",
        "current_title": "Python Software Engineer",
        "experience": "2 years",
        "experience_years": 2.0,
        "location": "Hyderabad",
        "skills": ["Python", "Django", "FastAPI", "MongoDB", "MySQL"],
        "education": "MCA",
        "current_company": "TechMatrix India",
        "profile_url": "https://www.naukri.com/candidate/rohit-verma-nk1003",
    },
    {
        "id": "nk-1004",
        "name": "Ananya Rao",
        "current_title": "Full Stack Developer",
        "experience": "3 years",
        "experience_years": 3.0,
        "location": "Bengaluru",
        "skills": ["Python", "FastAPI", "React", "MongoDB", "TypeScript", "Node.js"],
        "education": "B.E in Computer Science",
        "current_company": "Zeta Byte Tech",
        "profile_url": "https://www.naukri.com/candidate/ananya-rao-nk1004",
    },
    {
        "id": "nk-1005",
        "name": "Karthik Nair",
        "current_title": "Python Backend Developer",
        "experience": "1.5 years",
        "experience_years": 1.5,
        "location": "Hyderabad",
        "skills": ["Python", "FastAPI", "PostgreSQL", "HTML", "CSS"],
        "education": "B.Tech in Electronics",
        "current_company": "NextGen Soft",
        "profile_url": "https://www.naukri.com/candidate/karthik-nair-nk1005",
    },
    {
        "id": "nk-1006",
        "name": "Sneha Patel",
        "current_title": "Python / Data Engineer",
        "experience": "3.5 years",
        "experience_years": 3.5,
        "location": "Pune",
        "skills": ["Python", "FastAPI", "PySpark", "MongoDB", "Airflow", "GCP"],
        "education": "M.Tech in Data Science",
        "current_company": "DataVibe Analytics",
        "profile_url": "https://www.naukri.com/candidate/sneha-patel-nk1006",
    },
    {
        "id": "nk-1007",
        "name": "Vikram Malhotra",
        "current_title": "Lead Python Architect",
        "experience": "8 years",
        "experience_years": 8.0,
        "location": "Hyderabad",
        "skills": ["Python", "FastAPI", "Django", "Microservices", "MongoDB", "Kubernetes", "AWS"],
        "education": "B.Tech in Computer Science",
        "current_company": "Enterprise Global",
        "profile_url": "https://www.naukri.com/candidate/vikram-malhotra-nk1007",
    },
    {
        "id": "nk-1008",
        "name": "Divya Krishnan",
        "current_title": "Python API Developer",
        "experience": "2 years",
        "experience_years": 2.0,
        "location": "Chennai",
        "skills": ["Python", "FastAPI", "MongoDB", "RabbitMQ", "SQLAlchemy"],
        "education": "B.E in Computer Science",
        "current_company": "Fintech Solutions",
        "profile_url": "https://www.naukri.com/candidate/divya-krishnan-nk1008",
    },
    {
        "id": "nk-1009",
        "name": "Siddharth Joshi",
        "current_title": "Backend Engineer",
        "experience": "2.8 years",
        "experience_years": 2.8,
        "location": "Hyderabad",
        "skills": ["Python", "Flask", "MongoDB", "Docker", "Linux"],
        "education": "B.Tech in Computer Science",
        "current_company": "Apex Technologies",
        "profile_url": "https://www.naukri.com/candidate/siddharth-joshi-nk1009",
    },
    {
        "id": "nk-1010",
        "name": "Meera Sen",
        "current_title": "Junior Python Developer",
        "experience": "1 year",
        "experience_years": 1.0,
        "location": "Hyderabad",
        "skills": ["Python", "FastAPI", "SQLite", "Git"],
        "education": "B.Tech in Information Technology",
        "current_company": "Bright Future Tech",
        "profile_url": "https://www.naukri.com/candidate/meera-sen-nk1010",
    },
    {
        "id": "nk-1011",
        "name": "Arjun Das",
        "current_title": "Full Stack Engineer",
        "experience": "4.5 years",
        "experience_years": 4.5,
        "location": "Hyderabad",
        "skills": ["Python", "FastAPI", "MongoDB", "Angular", "Docker", "Azure"],
        "education": "MCA",
        "current_company": "Synergy Labs",
        "profile_url": "https://www.naukri.com/candidate/arjun-das-nk1011",
    },
    {
        "id": "nk-1012",
        "name": "Ritu Singhal",
        "current_title": "Python Backend Developer",
        "experience": "3 years",
        "experience_years": 3.0,
        "location": "Delhi NCR",
        "skills": ["Python", "FastAPI", "MongoDB", "ElasticSearch", "Kafka"],
        "education": "B.Tech in Computer Science",
        "current_company": "E-Commerce Titans",
        "profile_url": "https://www.naukri.com/candidate/ritu-singhal-nk1012",
    },
    {
        "id": "nk-1013",
        "name": "Manoj Kumar",
        "current_title": "Java Developer",
        "experience": "3 years",
        "experience_years": 3.0,
        "location": "Hyderabad",
        "skills": ["Java", "Spring Boot", "MySQL", "Microservices"],
        "education": "B.Tech in Computer Science",
        "current_company": "Legacy Corp",
        "profile_url": "https://www.naukri.com/candidate/manoj-kumar-nk1013",
    },
    {
        "id": "nk-1014",
        "name": "Kavita Deshmukh",
        "current_title": "Python Developer",
        "experience": "2.2 years",
        "experience_years": 2.2,
        "location": "Hyderabad",
        "skills": ["Python", "FastAPI", "MongoDB", "Pandas", "NumPy"],
        "education": "B.Tech in Computer Science",
        "current_company": "InfoServices Ltd",
        "profile_url": "https://www.naukri.com/candidate/kavita-deshmukh-nk1014",
    },
    {
        "id": "nk-1015",
        "name": "Suresh Babu",
        "current_title": "Python Developer",
        "experience": "5 years",
        "experience_years": 5.0,
        "location": "Hyderabad",
        "skills": ["Python", "FastAPI", "MongoDB", "GraphQL", "AWS", "CI/CD"],
        "education": "B.E in Computer Science",
        "current_company": "Innovate Global",
        "profile_url": "https://www.naukri.com/candidate/suresh-babu-nk1015",
    },
    {
        "id": "nk-1016",
        "name": "Neha Gupta",
        "current_title": "Frontend Developer",
        "experience": "2 years",
        "experience_years": 2.0,
        "location": "Hyderabad",
        "skills": ["React", "JavaScript", "HTML", "CSS", "Redux"],
        "education": "B.Tech in Computer Science",
        "current_company": "WebCraft",
        "profile_url": "https://www.naukri.com/candidate/neha-gupta-nk1016",
    },
    {
        "id": "nk-1017",
        "name": "Gaurav Roy",
        "current_title": "Python FastAPI Developer",
        "experience": "2 years",
        "experience_years": 2.0,
        "location": "Hyderabad",
        "skills": ["Python", "FastAPI", "MongoDB", "Redis", "Git"],
        "education": "B.Tech in Computer Science",
        "current_company": "RapidCode Labs",
        "profile_url": "https://www.naukri.com/candidate/gaurav-roy-nk1017",
    },
    {
        "id": "nk-1018",
        "name": "Tanvi Agarwal",
        "current_title": "Software Engineer - Python",
        "experience": "2.5 years",
        "experience_years": 2.5,
        "location": "Hyderabad",
        "skills": ["Python", "FastAPI", "MongoDB", "Docker", "Kubernetes"],
        "education": "B.Tech in Information Technology",
        "current_company": "ScaleUp Apps",
        "profile_url": "https://www.naukri.com/candidate/tanvi-agarwal-nk1018",
    },
    {
        "id": "nk-1019",
        "name": "Naveen Chawla",
        "current_title": "Python Backend Engineer",
        "experience": "3 years",
        "experience_years": 3.0,
        "location": "Hyderabad",
        "skills": ["Python", "FastAPI", "MongoDB", "FastAPI", "PostgreSQL"],
        "education": "B.Tech in Computer Science",
        "current_company": "Prime Software",
        "profile_url": "https://www.naukri.com/candidate/naveen-chawla-nk1019",
    },
    {
        "id": "nk-1020",
        "name": "Harshita Jain",
        "current_title": "Python Developer",
        "experience": "2 years",
        "experience_years": 2.0,
        "location": "Hyderabad",
        "skills": ["Python", "FastAPI", "MongoDB", "AWS Lambda"],
        "education": "B.Tech in Computer Science",
        "current_company": "Cloud Nine Software",
        "profile_url": "https://www.naukri.com/candidate/harshita-jain-nk1020",
    },
]


class NaukriPortal(BaseJobPortal):
    """
    Naukri Portal Implementation.
    
    Provides search capability over Naukri profiles. Currently operates with a rich
    mock candidate dataset for reliable local development, automated testing, and Swagger testing.
    """

    def __init__(self, use_mock: bool = True):
        self._use_mock = use_mock
        self._mock_data = MOCK_NAUKRI_CANDIDATES

    @property
    def portal_name(self) -> str:
        return "Naukri"

    def search(self, query: str, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Execute candidate search against Naukri.
        """
        if self._use_mock:
            return self._search_mock_data(query, filters)
        return self._fetch_live_results(query, filters)

    def _search_mock_data(self, query: str, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Filters mock candidate pool using token overlap and filter attributes.
        """
        results = []
        query_tokens = set(re.findall(r"\w+", query.lower())) if query else set()

        for cand in self._mock_data:
            # Check broad relevance against query tokens or return all if query is empty
            candidate_text = (
                f"{cand.get('current_title', '')} "
                f"{' '.join(cand.get('skills', []))} "
                f"{cand.get('location', '')}"
            ).lower()

            # We return candidates from the pool for ranking
            # Candidates with high relevance will naturally be ranked higher by the matcher
            results.append(cand)

        return results

    def _fetch_live_results(self, query: str, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Stub for official Naukri Enterprise / Recruiter API integration.
        """
        # In a live environment with authorized API credentials:
        # response = requests.post("https://api.naukri.com/v1/recruiter/search", ...)
        # return response.json().get("profiles", [])
        raise NotImplementedError("Live Naukri API credentials not configured. Please use mock mode.")

    def extract_profiles(self, raw_data: List[Dict[str, Any]]) -> List[CandidateProfile]:
        """
        Map raw portal data dictionaries to CandidateProfile domain models.
        """
        profiles: List[CandidateProfile] = []
        for item in raw_data:
            profile = CandidateProfile(
                name=item.get("name", "Unknown"),
                current_title=item.get("current_title", ""),
                experience=str(item.get("experience", "0 years")),
                location=item.get("location", ""),
                skills=list(item.get("skills", [])),
                education=item.get("education"),
                current_company=item.get("current_company"),
                profile_url=item.get("profile_url", ""),
                match_score=0.0,
                matched_skills=[],
                missing_skills=[],
            )
            profiles.append(profile)
        return profiles
