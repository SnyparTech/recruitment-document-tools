import pytest
from app.agents.requirement_agent import RequirementAgent
from app.schemas.search_plan import SearchPlan


@pytest.fixture
def agent():
    # Force rule engine during unit testing for deterministic tests
    return RequirementAgent(api_key=None)


def test_requirement_agent_skills_extraction(agent):
    req = "Looking for Python, FastAPI, Machine Learning, and NLP developers."
    plan = agent.generate_search_plan(req)

    assert plan.keywords is not None
    assert "Python" in plan.keywords.required
    assert "FastAPI" in plan.keywords.required
    assert "Machine Learning" in plan.keywords.required
    assert "NLP" in plan.keywords.required


def test_requirement_agent_required_vs_preferred(agent):
    req = "Mandatory skills are Python and FastAPI. Preferred skills: Docker and Kubernetes."
    plan = agent.generate_search_plan(req)

    assert plan.keywords is not None
    assert "Python" in plan.keywords.required
    assert "FastAPI" in plan.keywords.required
    assert "Docker" in plan.keywords.preferred
    assert "Kubernetes" in plan.keywords.preferred


def test_requirement_agent_experience_extraction(agent):
    # Range
    p1 = agent.generate_search_plan("Find engineers with 2 to 5 years experience")
    assert p1.min_experience == 2.0
    assert p1.max_experience == 5.0

    # Min only
    p2 = agent.generate_search_plan("Requires at least 3 years experience")
    assert p2.min_experience == 3.0
    assert p2.max_experience is None

    # Max only
    p3 = agent.generate_search_plan("Candidates with up to 5 years experience")
    assert p3.min_experience is None
    assert p3.max_experience == 5.0

    # Fresher
    p4 = agent.generate_search_plan("Looking for fresher software engineer")
    assert p4.min_experience == 0.0
    assert p4.max_experience == 1.0


def test_requirement_agent_location_normalization(agent):
    p1 = agent.generate_search_plan("Python developers in Hyd willing to relocate")
    assert p1.current_location == ["Hyderabad"]
    assert p1.include_relocation is True

    p2 = agent.generate_search_plan("Data engineers in Bangalore and Pune")
    assert "Bengaluru" in p2.current_location
    assert "Pune" in p2.current_location


def test_requirement_agent_salary_extraction(agent):
    # Range
    p1 = agent.generate_search_plan("Salary range 8 to 15 LPA")
    assert p1.salary is not None
    assert p1.salary.currency == "INR"
    assert p1.salary.min == 8.0
    assert p1.salary.max == 15.0

    # Max only
    p2 = agent.generate_search_plan("Budget below 12 LPA")
    assert p2.salary is not None
    assert p2.salary.min is None
    assert p2.salary.max == 12.0


def test_requirement_agent_notice_period_normalization(agent):
    p1 = agent.generate_search_plan("Need immediate joiner for frontend role")
    assert p1.notice_period == ["0-15 days"]

    p2 = agent.generate_search_plan("Candidates who can join within 15 days")
    assert p2.notice_period == ["0-15 days"]

    p3 = agent.generate_search_plan("Notice period should be within 1 month")
    assert p3.notice_period == ["1 month"]


def test_requirement_agent_null_unmentioned_fields(agent):
    req = "Looking for a Python developer in Hyderabad"
    plan = agent.generate_search_plan(req)

    # Specified fields
    assert "Python" in plan.keywords.required
    assert plan.current_location == ["Hyderabad"]

    # Unmentioned fields must remain None
    assert plan.min_experience is None
    assert plan.max_experience is None
    assert plan.salary is None
    assert plan.notice_period is None
    assert plan.gender is None
    assert plan.career_break is None
    assert plan.differently_abled is None
    assert plan.defence_background is None
    assert plan.candidate_category is None
    assert plan.candidate_age is None


def test_requirement_agent_full_example_search_plan(agent):
    req = (
        "Find AI/ML engineers in Hyderabad with 2 to 5 years of experience. "
        "Python, FastAPI, Machine Learning and NLP are mandatory. "
        "Salary should be 8 to 15 LPA. Prefer candidates who can join within 15 days."
    )
    plan = agent.generate_search_plan(req)

    assert plan.keywords is not None
    assert set(plan.keywords.required) == {"Python", "FastAPI", "Machine Learning", "NLP"}
    assert plan.keywords.mandatory is True
    assert plan.min_experience == 2.0
    assert plan.max_experience == 5.0
    assert plan.current_location == ["Hyderabad"]
    assert plan.salary.min == 8.0
    assert plan.salary.max == 15.0
    assert plan.salary.currency == "INR"
    assert plan.notice_period == ["0-15 days"]
    assert plan.department_role == ["AI/ML Engineer"]
    assert plan.confidence >= 0.9
