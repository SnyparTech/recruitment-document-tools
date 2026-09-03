from fastapi import APIRouter, status
from app.schemas.requirement import (
    CandidateSearchRequest,
    CandidateSearchResponse,
)
from app.services.form_service import FormService

router = APIRouter(prefix="/search", tags=["Candidate Search"])

form_service = FormService()


@router.post(
    "/candidates",
    response_model=CandidateSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate SearchPlan, Validate against Resdex Schema, and Optionally Execute Selenium",
    description=(
        "Schema-driven AI candidate search endpoint for Naukri Resdex:\n"
        "1. Requirement Agent converts natural language prompt into a structured SearchPlan.\n"
        "2. Validation Service validates the SearchPlan against resdex_schema.json.\n"
        "3. If execute=false (default), returns the SearchPlan and validation report (dry-run).\n"
        "4. If execute=true & submit_search=false, Selenium opens Resdex and fills the form for inspection without submitting.\n"
        "5. If execute=true & submit_search=true, Selenium fills the form and executes the search."
    ),
)
async def search_candidates(
    request: CandidateSearchRequest,
) -> CandidateSearchResponse:
    """
    Schema-driven Resdex candidate search endpoint.
    """
    return form_service.process_search_request(request)
