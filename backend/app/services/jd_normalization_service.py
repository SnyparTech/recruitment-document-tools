"""
JDNormalizationService — deterministic, non-LLM cleanup of a validated
ExtractedJD (dedupe/trim lists, canonicalize known skill aliases, normalize
employment_type wording) plus the deterministic hash used for duplicate
detection.

This is intentionally NOT another LLM call: normalization must be
reproducible so the same JD always hashes the same way, and defense-in-depth
against the extraction model not perfectly following its own alias-
normalization instructions.

Named `jd_normalization_service.py` to avoid colliding with any future
same-named service in another domain (mirrors jd_validation_service.py).
"""
import hashlib
import json
import re
from typing import Optional

from app.schemas.jd import ExtractedJD

# A small, obviously-safe set of common aliases. Deliberately conservative —
# this must never merge two genuinely different skills together.
_SKILL_ALIASES = {
    "reactjs": "React",
    "react.js": "React",
    "nodejs": "Node.js",
    "node": "Node.js",
    "js": "JavaScript",
    "javascript": "JavaScript",
    "ts": "TypeScript",
    "typescript": "TypeScript",
    "py": "Python",
    "python3": "Python",
    "mongo": "MongoDB",
    "mongodb": "MongoDB",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "k8s": "Kubernetes",
    "kubernetes": "Kubernetes",
    "aws": "AWS",
    "gcp": "GCP",
    "ml": "Machine Learning",
    "ai": "Artificial Intelligence",
}

_EMPLOYMENT_TYPE_MAP = {
    "full time": "Full Time",
    "fulltime": "Full Time",
    "full-time": "Full Time",
    "part time": "Part Time",
    "parttime": "Part Time",
    "part-time": "Part Time",
    "contract": "Contract",
    "contractual": "Contract",
    "internship": "Internship",
    "intern": "Internship",
    "freelance": "Freelance",
}


def _normalize_skill(skill: str) -> str:
    key = skill.strip().lower()
    return _SKILL_ALIASES.get(key, skill.strip())


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen = set()
    out = []
    for item in items:
        norm = item.strip()
        if not norm:
            continue
        key = norm.lower()
        if key not in seen:
            seen.add(key)
            out.append(norm)
    return out


class JDNormalizationService:
    def normalize(self, jd: ExtractedJD) -> ExtractedJD:
        data = jd.model_dump()

        data["skills"] = _dedupe_preserve_order([_normalize_skill(s) for s in data.get("skills", [])])
        data["mandatory_skills"] = _dedupe_preserve_order(
            [_normalize_skill(s) for s in data.get("mandatory_skills", [])]
        )
        data["preferred_skills"] = _dedupe_preserve_order(
            [_normalize_skill(s) for s in data.get("preferred_skills", [])]
        )
        data["location"] = _dedupe_preserve_order(data.get("location", []))
        data["requirements"] = _dedupe_preserve_order(data.get("requirements", []))

        if data.get("employment_type"):
            key = data["employment_type"].strip().lower()
            data["employment_type"] = _EMPLOYMENT_TYPE_MAP.get(key, data["employment_type"].strip())

        if data.get("company"):
            data["company"] = data["company"].strip()
        if data.get("job_title"):
            data["job_title"] = data["job_title"].strip()

        return ExtractedJD.model_validate(data)

    def compute_hash(self, normalized_jd: ExtractedJD) -> str:
        """
        Deterministic hash over the fields that define "is this the same job
        posting" — deliberately excludes job_description (free text that can
        vary slightly between re-sends of the same role) and confidence
        (extraction metadata, not JD content).
        """
        key_fields = {
            "job_title": (normalized_jd.job_title or "").strip().lower(),
            "company": (normalized_jd.company or "").strip().lower(),
            "location": sorted(l.strip().lower() for l in normalized_jd.location),
            "skills": sorted(s.strip().lower() for s in normalized_jd.skills),
            "experience": normalized_jd.experience.model_dump() if normalized_jd.experience else None,
            "employment_type": (normalized_jd.employment_type or "").strip().lower(),
        }
        canonical = json.dumps(key_fields, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
