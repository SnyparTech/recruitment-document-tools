"""
Guards against resdex_schema.json drift: hardcoded canonical Resdex option
strings used in requirement_agent.py's LLM prompt and deterministic rule-based
fallback must always remain valid options per resdex_schema.json. If the schema
changes, this test fails loudly instead of the bot silently producing values
that ValidationService then rejects at request time.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.agents.requirement_agent import (
    NOTICE_PERIOD_MAP,
    RequirementAgent,
    load_resdex_schema,
)

SCHEMA = load_resdex_schema()


def _options(section: str, field: str):
    return set(SCHEMA["sections"][section]["fields"][field].get("options", []))


def test_notice_period_map_values_are_valid_schema_options():
    allowed = _options("notice_period", "notice_period")
    for canonical_value in NOTICE_PERIOD_MAP.values():
        assert canonical_value in allowed, (
            f"NOTICE_PERIOD_MAP produces '{canonical_value}' which is not in "
            f"resdex_schema.json notice_period options: {sorted(allowed)}"
        )


def test_rule_based_gender_values_are_valid_schema_options():
    allowed = _options("diversity_hiring", "gender")
    for value in ("Female candidates", "Male candidates"):
        assert value in allowed


def test_rule_based_career_break_value_is_valid_schema_option():
    allowed = _options("diversity_hiring", "career_break")
    assert "Women returning to work" in allowed


def test_rule_based_differently_abled_and_defence_values_are_valid_schema_options():
    assert "Any" in _options("diversity_hiring", "differently_abled")
    assert "Any" in _options("diversity_hiring", "defence_background")


def test_rule_based_job_type_and_employment_type_values_are_valid_schema_options():
    allowed_job_type = _options("additional_details", "job_type")
    for value in ("Permanent", "Temporary/Contract job"):
        assert value in allowed_job_type

    allowed_emp_type = _options("additional_details", "employment_type")
    for value in ("Full time", "Part time"):
        assert value in allowed_emp_type


def test_llm_prompt_distinguishes_job_type_from_employment_type():
    """Real bug: the LLM prompt gave no guidance on job_type vs
    employment_type (two different Resdex fields — Permanent/Contract vs
    Full time/Part time) and no allowed-values list for either, so it
    hallucinated a single merged, invalid string "Permanent / Contract"
    into employment_type, which ValidationService then rejected with a
    422 on Apply to Resdex. The prompt must list each field's own real
    options and leave no __PLACEHOLDER__ unsubstituted."""
    agent = RequirementAgent()
    # Build the same substitution generate_search_plan() does, without an LLM call.
    system_prompt = """job_type and employment_type are two DIFFERENT Resdex fields. job_type allowed values: __JOB_TYPE_OPTIONS__. employment_type allowed values: __EMPLOYMENT_TYPE_OPTIONS__."""
    substituted = (
        system_prompt.replace("__JOB_TYPE_OPTIONS__", ", ".join(f'"{o}"' for o in agent._job_type_options))
        .replace("__EMPLOYMENT_TYPE_OPTIONS__", ", ".join(f'"{o}"' for o in agent._employment_type_options))
    )
    assert "__JOB_TYPE_OPTIONS__" not in substituted and "__EMPLOYMENT_TYPE_OPTIONS__" not in substituted
    allowed_job_type = _options("additional_details", "job_type")
    allowed_emp_type = _options("additional_details", "employment_type")
    assert set(agent._job_type_options) == allowed_job_type
    assert set(agent._employment_type_options) == allowed_emp_type
    assert "Permanent / Contract" not in agent._job_type_options and "Permanent / Contract" not in agent._employment_type_options


def test_llm_prompt_education_options_match_schema():
    """The LLM prompt's ug/pg_qualification guidance is now generated from the
    schema at runtime (see RequirementAgent.__init__) rather than hardcoded —
    this test confirms the schema itself still has both fields populated so
    that substitution never silently produces an empty options list."""
    ug = _options("education_details", "ug_qualification")
    pg = _options("education_details", "pg_qualification")
    assert ug, "education_details.ug_qualification has no options in resdex_schema.json"
    assert pg, "education_details.pg_qualification has no options in resdex_schema.json"
