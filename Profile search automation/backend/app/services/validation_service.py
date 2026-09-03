import json
import logging
import os
from typing import Any, Dict, List
from app.agents.requirement_agent import load_resdex_schema
from app.schemas.requirement import ValidationResult
from app.schemas.search_plan import SearchPlan

logger = logging.getLogger(__name__)


class ValidationService:
    """
    Validates generated SearchPlan objects against resdex_schema.json.
    Ensures invalid or unallowed values never reach Selenium.
    """

    def __init__(self, schema: Dict[str, Any] = None):
        self.schema = schema or load_resdex_schema()
        self._extract_allowed_options()

    def _extract_allowed_options(self) -> None:
        """Extracts allowed option sets from the semantic Resdex schema."""
        sections = self.schema.get("sections", {})

        # Notice period options
        np_field = (
            sections.get("notice_period", {})
            .get("fields", {})
            .get("notice_period", {})
        )
        self.allowed_notice_periods = set(np_field.get("options", []))

        # Diversity options
        div_fields = sections.get("diversity_hiring", {}).get("fields", {})
        self.allowed_genders = set(div_fields.get("gender", {}).get("options", []))
        self.allowed_differently_abled = set(
            div_fields.get("differently_abled", {}).get("options", [])
        )
        self.allowed_defence = set(
            div_fields.get("defence_background", {}).get("options", [])
        )

        # Additional details options
        add_fields = sections.get("additional_details", {}).get("fields", {})
        self.allowed_job_types = set(add_fields.get("job_type", {}).get("options", []))
        self.allowed_employment_types = set(
            add_fields.get("employment_type", {}).get("options", [])
        )
        self.allowed_categories = set(
            add_fields.get("candidate_category", {}).get("options", [])
        )

        # Active period options
        active_field = (
            sections.get("search_active_period", {})
            .get("fields", {})
            .get("active_in", {})
        )
        self.allowed_active_in = set(active_field.get("options", []))

        # Scope options
        basic_fields = sections.get("basic_search", {}).get("fields", {})
        kw_props = basic_fields.get("keywords", {}).get("properties", {})
        self.allowed_keyword_scopes = set(
            kw_props.get("search_scope", {}).get("options", [])
        )

    def validate(self, plan: SearchPlan) -> ValidationResult:
        """
        Validates the SearchPlan against Resdex schema constraints.
        Returns a ValidationResult object with boolean valid flag and list of errors.
        """
        errors: List[str] = []
        warnings: List[str] = []

        if not plan:
            return ValidationResult(
                valid=False, errors=["SearchPlan cannot be empty or null."]
            )

        # 1. Validate Notice Period
        if plan.notice_period:
            for np in plan.notice_period:
                if np not in self.allowed_notice_periods:
                    errors.append(
                        f"Invalid notice_period '{np}'. Allowed Resdex options are: {sorted(list(self.allowed_notice_periods))}"
                    )

        # 2. Validate Job Type
        if plan.job_type:
            if plan.job_type not in self.allowed_job_types:
                errors.append(
                    f"Invalid job_type '{plan.job_type}'. Allowed Resdex options are: {sorted(list(self.allowed_job_types))}"
                )

        # 3. Validate Employment Type
        if plan.employment_type:
            if plan.employment_type not in self.allowed_employment_types:
                errors.append(
                    f"Invalid employment_type '{plan.employment_type}'. Allowed Resdex options are: {sorted(list(self.allowed_employment_types))}"
                )

        # 4. Validate Gender
        if plan.gender:
            if plan.gender not in self.allowed_genders:
                errors.append(
                    f"Invalid gender '{plan.gender}'. Allowed Resdex options are: {sorted(list(self.allowed_genders))}"
                )

        # 5. Validate Active In
        if plan.active_in:
            if plan.active_in not in self.allowed_active_in:
                errors.append(
                    f"Invalid active_in period '{plan.active_in}'. Allowed Resdex options are: {sorted(list(self.allowed_active_in))}"
                )

        # 6. Validate Keyword Search Scope
        if plan.keywords and plan.keywords.search_scope:
            if plan.keywords.search_scope not in self.allowed_keyword_scopes:
                errors.append(
                    f"Invalid keyword search_scope '{plan.keywords.search_scope}'. Allowed options are: {sorted(list(self.allowed_keyword_scopes))}"
                )

        # 7. Validate Experience Bounds
        if plan.min_experience is not None and plan.max_experience is not None:
            if plan.min_experience > plan.max_experience:
                errors.append(
                    f"min_experience ({plan.min_experience}) cannot be greater than max_experience ({plan.max_experience})."
                )

        # 8. Validate Salary Bounds
        if plan.salary:
            if plan.salary.min is not None and plan.salary.max is not None:
                if plan.salary.min > plan.salary.max:
                    errors.append(
                        f"salary.min ({plan.salary.min}) cannot be greater than salary.max ({plan.salary.max})."
                    )

        # 9. Validate Candidate Age Bounds
        if plan.candidate_age:
            if plan.candidate_age.min is not None and plan.candidate_age.max is not None:
                if plan.candidate_age.min > plan.candidate_age.max:
                    errors.append(
                        f"candidate_age.min ({plan.candidate_age.min}) cannot be greater than candidate_age.max ({plan.candidate_age.max})."
                    )

        is_valid = len(errors) == 0
        return ValidationResult(valid=is_valid, errors=errors, warnings=warnings)
