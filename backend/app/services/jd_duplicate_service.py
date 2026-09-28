"""
JDDuplicateService — decides whether a normalized JD's hash has already been
seen. Deliberately thin: the actual lookup lives in JDRepository so this
service stays pure decision logic and is trivial to unit test with a fake
repository.

Named `jd_duplicate_service.py` (spec calls it "duplicate_service.py") to
match the jd_-prefixed naming used for the other new JD-domain services.
"""
import logging
from dataclasses import dataclass
from typing import Optional

from app.services.jd_repository import JDRepository

logger = logging.getLogger(__name__)


@dataclass
class DuplicateCheckResult:
    is_duplicate: bool
    existing_job_id: Optional[str] = None


class JDDuplicateService:
    def __init__(self, repository: Optional[JDRepository] = None):
        self.repository = repository or JDRepository()

    async def check(self, jd_hash: str) -> DuplicateCheckResult:
        existing = await self.repository.find_job_by_hash(jd_hash)
        if existing:
            logger.info("Duplicate JD detected (hash=%s, existing job_id=%s)", jd_hash, existing.get("_id"))
            return DuplicateCheckResult(is_duplicate=True, existing_job_id=existing.get("_id"))
        return DuplicateCheckResult(is_duplicate=False)
