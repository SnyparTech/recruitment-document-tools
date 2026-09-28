from app.services.jd_validation_service import JDValidationService


def test_valid_jd_passes():
    v, errors = JDValidationService().validate({
        "job_title": "Backend Engineer",
        "skills": ["Python", "FastAPI"],
        "location": ["Remote"],
    })
    assert errors == []
    assert v is not None
    assert v.job_title == "Backend Engineer"


def test_none_input_rejected():
    v, errors = JDValidationService().validate(None)
    assert v is None
    assert len(errors) == 1


def test_non_dict_input_rejected():
    v, errors = JDValidationService().validate(["not", "a", "dict"])
    assert v is None
    assert errors


def test_missing_job_title_rejected():
    v, errors = JDValidationService().validate({"skills": ["Python"]})
    assert v is None
    assert errors


def test_impossible_experience_range_rejected():
    v, errors = JDValidationService().validate({
        "job_title": "X",
        "experience": {"min_years": 10, "max_years": 2},
    })
    assert v is None
    assert any("min_years" in e for e in errors)


def test_invalid_salary_range_rejected():
    v, errors = JDValidationService().validate({
        "job_title": "X",
        "salary": {"min": 2000000, "max": 500000},
    })
    assert v is None
    assert any("salary" in e for e in errors)


def test_excessively_long_field_rejected():
    v, errors = JDValidationService().validate({"job_title": "X" * 500})
    assert v is None
    assert errors


def test_prompt_injection_style_script_tag_rejected():
    v, errors = JDValidationService().validate({
        "job_title": "Backend Engineer",
        "job_description": "Great role. <script>alert('xss')</script> Apply now.",
    })
    assert v is None
    assert any("Dangerous content" in e for e in errors)


def test_dangerous_content_nested_in_list_rejected():
    v, errors = JDValidationService().validate({
        "job_title": "Backend Engineer",
        "requirements": ["Normal requirement", "javascript:alert(1)"],
    })
    assert v is None
    assert any("Dangerous content" in e for e in errors)


def test_wrong_type_for_list_field_rejected():
    v, errors = JDValidationService().validate({"job_title": "X", "skills": "Python"})
    assert v is None
    assert errors
