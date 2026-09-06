import pytest
from app.schemas.search_plan import KeywordsPlan, SalaryPlan, SearchPlan
from app.services.validation_service import ValidationService


@pytest.fixture
def validator():
    return ValidationService()


def test_validation_valid_search_plan(validator):
    plan = SearchPlan(
        keywords=KeywordsPlan(
            required=["Python", "FastAPI"],
            mandatory=True,
            search_scope="Entire resume",
        ),
        min_experience=2.0,
        max_experience=5.0,
        current_location=["Hyderabad"],
        salary=SalaryPlan(currency="INR", min=8.0, max=15.0),
        notice_period=["0-15 days", "1 month"],
        job_type="Permanent",
        employment_type="Full time",
        active_in="6 months",
    )

    result = validator.validate(plan)
    assert result.valid is True
    assert len(result.errors) == 0


def test_validation_invalid_notice_period_rejection(validator):
    # '45 days' is NOT in allowed Resdex notice period options
    plan = SearchPlan(
        keywords=KeywordsPlan(required=["Python"]),
        notice_period=["45 days"],
    )

    result = validator.validate(plan)
    assert result.valid is False
    assert any("Invalid notice_period '45 days'" in err for err in result.errors)


def test_validation_invalid_job_type_rejection(validator):
    # 'Remote' is NOT a valid Resdex job_type option
    plan = SearchPlan(
        keywords=KeywordsPlan(required=["Python"]),
        job_type="Remote",
    )

    result = validator.validate(plan)
    assert result.valid is False
    assert any("Invalid job_type 'Remote'" in err for err in result.errors)


def test_validation_invalid_active_in_rejection(validator):
    # '1 year' is not an allowed active_in option
    plan = SearchPlan(
        keywords=KeywordsPlan(required=["Python"]),
        active_in="1 year",
    )

    result = validator.validate(plan)
    assert result.valid is False
    assert any("Invalid active_in period '1 year'" in err for err in result.errors)


def test_validation_invalid_experience_bounds(validator):
    # min > max
    plan = SearchPlan(
        min_experience=7.0,
        max_experience=3.0,
    )

    result = validator.validate(plan)
    assert result.valid is False
    assert any("min_experience (7.0) cannot be greater than max_experience (3.0)" in err for err in result.errors)


def test_validation_invalid_salary_bounds(validator):
    # min > max
    plan = SearchPlan(
        salary=SalaryPlan(currency="INR", min=20.0, max=10.0),
    )

    result = validator.validate(plan)
    assert result.valid is False
    assert any("salary.min (20.0) cannot be greater than salary.max (10.0)" in err for err in result.errors)
