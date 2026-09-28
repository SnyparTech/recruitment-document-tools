from app.schemas.jd import ExtractedJD
from app.services.jd_normalization_service import JDNormalizationService


def _jd(**kwargs) -> ExtractedJD:
    base = {"job_title": "Backend Engineer"}
    base.update(kwargs)
    return ExtractedJD.model_validate(base)


def test_skill_aliases_normalized():
    jd = _jd(skills=["reactjs", "nodejs", "py"])
    result = JDNormalizationService().normalize(jd)
    assert result.skills == ["React", "Node.js", "Python"]


def test_duplicate_skills_deduped_case_insensitively():
    jd = _jd(skills=["Python", "python", "PYTHON"])
    result = JDNormalizationService().normalize(jd)
    assert result.skills == ["Python"]


def test_employment_type_canonicalized():
    jd = _jd(employment_type="full-time")
    result = JDNormalizationService().normalize(jd)
    assert result.employment_type == "Full Time"


def test_location_deduped_preserving_first_casing():
    jd = _jd(location=["Bangalore", "bangalore", "Pune"])
    result = JDNormalizationService().normalize(jd)
    assert result.location == ["Bangalore", "Pune"]


def test_hash_is_deterministic_for_same_input():
    svc = JDNormalizationService()
    jd1 = svc.normalize(_jd(skills=["Python"], location=["Pune"]))
    jd2 = svc.normalize(_jd(skills=["Python"], location=["Pune"]))
    assert svc.compute_hash(jd1) == svc.compute_hash(jd2)


def test_hash_ignores_field_order_in_lists():
    svc = JDNormalizationService()
    jd1 = svc.normalize(_jd(skills=["Python", "React"], location=["Pune", "Remote"]))
    jd2 = svc.normalize(_jd(skills=["React", "Python"], location=["Remote", "Pune"]))
    assert svc.compute_hash(jd1) == svc.compute_hash(jd2)


def test_hash_differs_for_different_job_title():
    svc = JDNormalizationService()
    jd1 = svc.normalize(_jd(job_title="Backend Engineer"))
    jd2 = svc.normalize(_jd(job_title="Frontend Engineer"))
    assert svc.compute_hash(jd1) != svc.compute_hash(jd2)


def test_hash_excludes_job_description_text():
    svc = JDNormalizationService()
    jd1 = svc.normalize(_jd(job_description="Version one of the description."))
    jd2 = svc.normalize(_jd(job_description="A completely different description text."))
    assert svc.compute_hash(jd1) == svc.compute_hash(jd2)
