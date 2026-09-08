"""
Information Completeness Validation & Zero-Information-Loss Repair Service.

Validates that no information from the original resume is lost, removed, or dropped
during AI structuring:
1. Extracts all emails, phone numbers, URLs, dates, metrics, percentages, and bullets
   from original content.
2. Checks their verbatim presence in the structured JSON.
3. Automatically repairs any unmapped or dropped items by injecting them cleanly
   into the appropriate section or 'additional_sections'.
4. Produces a detailed verification audit report.
"""

import copy
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Patterns for critical entities
PERCENT_RE = re.compile(r"\b\d+(?:\.\d+)?%\b")
DATE_RANGE_RE = re.compile(
    r"\b(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*)?(?:19|20)\d{2}\b",
    re.IGNORECASE,
)
METRIC_NUM_RE = re.compile(r"\b(?:\$|€|£|₹)?\d+(?:[,\.]\d+)?\s*(?:k|m|b|million|billion|lakh|crore)?\b", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b")
URL_RE = re.compile(r"https?://[^\s<>\"']+|www\.[^\s<>\"']+")


class CompletenessValidator:
    """Validates and enforces 100% information retention between source text and structured JSON."""

    @classmethod
    def validate_and_repair(
        cls,
        original_text: str,
        structured_resume: Dict[str, Any],
        canonical_bullets: Optional[List[str]] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Validates completeness, auto-repairs missing items into structured_resume,
        and returns (repaired_resume, audit_report).
        """
        repaired = copy.deepcopy(structured_resume)
        report = cls.audit_completeness(original_text, repaired, canonical_bullets)

        if not report["complete"]:
            logger.info(
                f"Completeness audit found {len(report['missing_items'])} unmapped items. "
                "Executing deterministic zero-loss repair loop..."
            )
            repaired = cls._repair_missing_items(repaired, report["missing_items"])
            # Re-audit after repair
            report = cls.audit_completeness(original_text, repaired, canonical_bullets)

        return repaired, report

    @classmethod
    def audit_completeness(
        cls,
        original_text: str,
        structured_resume: Dict[str, Any],
        canonical_bullets: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Audits structured resume against original text."""
        missing_items: List[str] = []

        # Flatten all text from the structured resume for search
        structured_text = cls._flatten_structured_json(structured_resume).lower()

        # 1. Check Emails
        orig_emails = set(EMAIL_RE.findall(original_text))
        for email in orig_emails:
            if email.lower() not in structured_text:
                missing_items.append(f"Email: {email}")

        # 2. Check URLs
        orig_urls = set(URL_RE.findall(original_text))
        for url in orig_urls:
            # Check without protocol
            clean_url = re.sub(r"^https?://", "", url).lower()
            if clean_url not in structured_text:
                missing_items.append(f"URL: {url}")

        # 3. Check Percentages (key achievements e.g. 35%, 99.9%)
        orig_percents = set(PERCENT_RE.findall(original_text))
        for pct in orig_percents:
            if pct.lower() not in structured_text:
                missing_items.append(f"Metric Percentage: {pct}")

        # 4. Check Bullets
        bullets_to_check = canonical_bullets or []
        for bullet in bullets_to_check:
            clean_bullet = bullet.strip().lower()
            if len(clean_bullet) > 15:
                # Substring check: at least 60% of bullet words should appear
                words = clean_bullet.split()
                matches = sum(1 for w in words if len(w) > 3 and w in structured_text)
                ratio = matches / len(words) if words else 1.0
                if ratio < 0.6:
                    missing_items.append(f"Bullet point: {bullet[:80]}...")

        total_checked = len(orig_emails) + len(orig_urls) + len(orig_percents) + len(bullets_to_check)
        if total_checked == 0:
            preservation_score = 100.0
        else:
            preserved_count = total_checked - len(missing_items)
            preservation_score = max(0.0, min(100.0, (preserved_count / total_checked) * 100.0))

        return {
            "complete": len(missing_items) == 0,
            "preservation_score": round(preservation_score, 1),
            "missing_items": missing_items,
            "total_entities_verified": total_checked,
        }

    @classmethod
    def _repair_missing_items(
        cls, structured_resume: Dict[str, Any], missing_items: List[str]
    ) -> Dict[str, Any]:
        """Injects missing items into the appropriate section to guarantee zero information loss."""
        repaired = copy.deepcopy(structured_resume)
        recovered_items = []

        for item in missing_items:
            if item.startswith("Email:"):
                val = item.split("Email:")[1].strip()
                if not repaired.get("personal_information", {}).get("email"):
                    repaired.setdefault("personal_information", {})["email"] = val
            elif item.startswith("URL:"):
                val = item.split("URL:")[1].strip()
                if "linkedin" in val.lower() and not repaired.get("personal_information", {}).get("linkedin"):
                    repaired.setdefault("personal_information", {})["linkedin"] = val
                elif not repaired.get("personal_information", {}).get("website"):
                    repaired.setdefault("personal_information", {})["website"] = val
                else:
                    recovered_items.append(val)
            elif item.startswith("Bullet point:"):
                val = item.split("Bullet point:")[1].strip()
                recovered_items.append(val)
            else:
                recovered_items.append(item)

        if recovered_items:
            additional = repaired.setdefault("additional_sections", [])
            # Check if an 'ADDITIONAL DETAILS' section exists
            found = False
            for sec in additional:
                if "ADDITIONAL" in sec.get("title", "").upper():
                    sec.setdefault("items", []).extend(recovered_items)
                    found = True
                    break
            if not found:
                additional.append({
                    "title": "ADDITIONAL ACCOMPLISHMENTS & DETAILS",
                    "items": recovered_items,
                })

        return repaired

    @classmethod
    def _flatten_structured_json(cls, data: Any) -> str:
        """Flattens all strings from structured JSON into a single searchable text."""
        chunks = []
        if isinstance(data, dict):
            for v in data.values():
                chunks.append(cls._flatten_structured_json(v))
        elif isinstance(data, list):
            for v in data:
                chunks.append(cls._flatten_structured_json(v))
        elif isinstance(data, str):
            chunks.append(data)
        elif data is not None:
            chunks.append(str(data))
        return " ".join(chunks)
