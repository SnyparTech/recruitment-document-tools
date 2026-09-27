import logging

from fastapi import APIRouter, HTTPException, status

from app.schemas.jd import JDExtractionRequest, JDValidateRequest
from app.agents.jd_extraction_agent import JDExtractionAgent
from app.services.jd_validation_service import JDValidationService
from app.services.jd_repository import JDRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Jobs / JD"])

_agent = JDExtractionAgent()
_validation_service = JDValidationService()
_repository = JDRepository()


@router.post("/jd/extract", summary="Run the JD extraction agent on raw email text (manual test / Swagger)")
async def extract_jd(request: JDExtractionRequest):
    raw_jd = await _agent.extract(request.subject, request.body, request.attachment_text)
    if raw_jd is None:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail={
            "error": "JD_EXTRACTION_FAILED",
            "message": "JD extraction failed or returned no output (check GROQ_API_KEY / model availability).",
        })
    return {"extracted_jd": raw_jd}


@router.post("/jd/validate", summary="Validate an already-extracted JD dict against the strict schema")
async def validate_jd(request: JDValidateRequest):
    validated, errors = _validation_service.validate(request.extracted_jd)
    if validated is None:
        return {"valid": False, "errors": errors}
    return {"valid": True, "validated_jd": validated.model_dump(), "errors": []}


@router.get("/jobs", summary="List processed jobs")
async def list_jobs(limit: int = 50, skip: int = 0):
    jobs = await _repository.list_jobs(limit=limit, skip=skip)
    return {"count": len(jobs), "jobs": jobs}


@router.get("/jobs/{job_id}", summary="Get a single job by id")
async def get_job(job_id: str):
    job = await _repository.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={
            "error": "JOB_NOT_FOUND",
            "message": f"No job found with id {job_id}.",
        })
    return job


@router.get("/messages/{message_id}", summary="Get a single tracked WhatsApp message by id")
async def get_message(message_id: str):
    message = await _repository.get_message(message_id)
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={
            "error": "MESSAGE_NOT_FOUND",
            "message": f"No message found with id {message_id}.",
        })
    return message
