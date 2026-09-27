"""
JDValidationService — the mandatory gate between JDExtractionAgent's raw LLM
output and everything downstream. Nothing the LLM produced is trusted until
it has passed through here: Pydantic structural/type/range validation PLUS a
dangerous-content scan for injected markup that could execute if ever
rendered somewhere less careful than a WhatsApp text message.

Named `jd_validation_service.py` (not `validation_service.py`) to avoid
colliding with the pre-existing, unrelated `validation_service.py` that
validates Resdex SearchPlans for the candidate-search feature.
"""
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError

from app.schemas.jd import ExtractedJD

logger = logging.getLogger(__name__)

# Markup/script injection patterns — a JD is untrusted text; if the model
# echoed something like this back into a field, refuse to let it propagate
# any further (e.g. into a future HTML/dashboard rendering of stored JDs).
_DANGEROUS_PATTERNS = [
    re.compile(r"<\s*script", re.IGNORECASE),
    re.compile(r"<\s*iframe", re.IGNORECASE),
    re.compile(r"javascript\s*:", re.IGNORECASE),
    re.compile(r"data\s*:\s*text/html", re.IGNORECASE),
    re.compile(r"on(?:error|load|click)\s*=", re.IGNORECASE),
]


def _scan_dangerous_content(value: Any, path: str, errors: List[str]) -> None:
    if isinstance(value, str):
        for pattern in _DANGEROUS_PATTERNS:
            if pattern.search(value):
                errors.append(f"Dangerous content detected in field '{path}' (matched {pattern.pattern!r}).")
                return
    elif isinstance(value, list):
        for i, item in enumerate(value):
            _scan_dangerous_content(item, f"{path}[{i}]", errors)
    elif isinstance(value, dict):
        for k, v in value.items():
            _scan_dangerous_content(v, f"{path}.{k}", errors)


class JDValidationService:
    def validate(self, raw_jd: Optional[Dict[str, Any]]) -> Tuple[Optional[ExtractedJD], List[str]]:
        """
        Returns (validated_jd_or_None, errors). validated_jd is None if and
        only if errors is non-empty — callers should treat that as a hard
        stop (per the pipeline's "validation FAILED -> do not continue" rule).
        """
        if raw_jd is None:
            return None, ["JD extraction produced no output (empty or unparseable LLM response)."]

        if not isinstance(raw_jd, dict):
            return None, [f"Extracted JD must be a JSON object, got {type(raw_jd).__name__}."]

        try:
            validated = ExtractedJD.model_validate(raw_jd)
        except ValidationError as exc:
            errors = [f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}" for e in exc.errors()]
            return None, errors

        dangerous: List[str] = []
        _scan_dangerous_content(validated.model_dump(), "extracted_jd", dangerous)
        if dangerous:
            return None, dangerous

        return validated, []
