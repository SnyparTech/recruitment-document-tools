import pytest
from app.models.requirement import ParsedRequirement
from app.services.query_generator import SearchQueryGenerator
from app.services.requirement_parser import RequirementParser


def test_requirement_parser_basic():
    parser = RequirementParser()
    text = "Find AI/ML Engineers in Hyderabad with 1-3 years experience and skills Python, FastAPI, Machine Learning and NLP"
    parsed = parser.parse(text)

    assert parsed.role == "AI/ML Engineer"
    assert "Python" in parsed.required_skills
    assert "FastAPI" in parsed.required_skills
    assert "Machine Learning" in parsed.required_skills
    assert "NLP" in parsed.required_skills
    assert parsed.location == "Hyderabad"
    assert parsed.experience is not None
    assert parsed.experience.min_years == 1.0
    assert parsed.experience.max_years == 3.0
    assert parsed.education is None


def test_requirement_parser_skill_aliases():
    parser = RequirementParser()
    text = "Need developer with ML, GenAI, Postgres, TS, and Docker in Bengaluru"
    parsed = parser.parse(text)

    assert "Machine Learning" in parsed.required_skills
    assert "Generative AI" in parsed.required_skills
    assert "PostgreSQL" in parsed.required_skills
    assert "TypeScript" in parsed.required_skills
    assert "Docker" in parsed.required_skills


def test_requirement_parser_experience_variations():
    parser = RequirementParser()

    # Plus pattern
    res1 = parser.parse("Senior Python Engineer with 3+ years experience in Pune")
    assert res1.experience is not None
    assert res1.experience.min_years == 3.0
    assert res1.experience.max_years is None

    # Range pattern
    res2 = parser.parse("Looking for Backend Developer having 2-5 yrs exp in Mumbai")
    assert res2.experience is not None
    assert res2.experience.min_years == 2.0
    assert res2.experience.max_years == 5.0

    # Min pattern
    res3 = parser.parse("Hiring Data Scientist with at least 4 years of experience")
    assert res3.experience is not None
    assert res3.experience.min_years == 4.0


def test_requirement_parser_location_and_education():
    parser = RequirementParser()
    text = "Hiring Python Developer with B.Tech degree in Bangalore"
    parsed = parser.parse(text)

    assert parsed.location == "Bengaluru"
    assert parsed.education == "B.Tech"


def test_search_query_generator():
    parser = RequirementParser()
    generator = SearchQueryGenerator()

    text = "Find AI/ML Engineers in Hyderabad with 1-3 years experience and skills Python, FastAPI, Machine Learning and NLP"
    parsed = parser.parse(text)
    query = generator.generate(parsed)

    assert "AI ML Engineer" in query.primary_query
    assert "Python" in query.primary_query
    assert "FastAPI" in query.primary_query
    assert "Machine Learning" in query.primary_query
    assert "NLP" in query.primary_query
    assert "AI Engineer" in query.role_keywords
    assert "ML Engineer" in query.role_keywords
    assert query.location == "Hyderabad"
    assert query.min_experience == 1.0
    assert query.max_experience == 3.0
