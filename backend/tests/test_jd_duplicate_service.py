from unittest.mock import AsyncMock

from app.services.jd_duplicate_service import JDDuplicateService


async def test_no_existing_job_is_not_duplicate():
    repo = AsyncMock()
    repo.find_job_by_hash.return_value = None

    result = await JDDuplicateService(repository=repo).check("somehash")

    assert result.is_duplicate is False
    assert result.existing_job_id is None


async def test_existing_job_is_duplicate():
    repo = AsyncMock()
    repo.find_job_by_hash.return_value = {"_id": "job-existing-1"}

    result = await JDDuplicateService(repository=repo).check("somehash")

    assert result.is_duplicate is True
    assert result.existing_job_id == "job-existing-1"
