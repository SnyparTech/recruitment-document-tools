import io
import logging
import os
import re
import time
from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
import fitz  # PyMuPDF
import docx

from app.schemas.requirement import (
    CandidateSearchRequest,
    CandidateSearchResponse,
    ExecutionResult,
    ValidationResult,
)
from app.schemas.search_plan import SearchPlan
from app.services.form_service import FormService
from app.portals.naukri_resdex import NaukriResdexPortal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["Candidate Search"])

form_service = FormService()

ALLOWED_DOC_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


_latest_search_plan = None
_latest_plan_timestamp = 0.0


@router.get(
    "/active-plan",
    summary="Get active SearchPlan for Naukri Resdex browser auto-fill",
)
async def get_active_plan():
    """Returns the latest SearchPlan for the extension or bookmarklet to auto-fill."""
    global _latest_search_plan, _latest_plan_timestamp
    return {
        "status": "success",
        "has_plan": _latest_search_plan is not None,
        "timestamp": _latest_plan_timestamp,
        "plan": _latest_search_plan,
    }


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
    global _latest_search_plan, _latest_plan_timestamp
    response = form_service.process_search_request(request)
    if response and response.search_plan:
        _latest_search_plan = response.search_plan.model_dump()
        _latest_plan_timestamp = time.time()
    return response


class DirectSearchPlanRequest(BaseModel):
    """Request schema for direct SearchPlan execution (bypasses LLM parsing)."""

    plan: SearchPlan = Field(..., description="Pre-built SearchPlan to execute directly")
    execute: bool = Field(
        default=False,
        description="Whether to execute Selenium form filling",
    )
    submit_search: bool = Field(
        default=False,
        description="Whether to submit the search after filling form fields",
    )


@router.post(
    "/plan",
    response_model=CandidateSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute a pre-built SearchPlan directly (bypasses LLM requirement parsing)",
    description=(
        "Accepts a complete SearchPlan JSON and executes it directly on Resdex.\n"
        "Use this endpoint when you already have a validated SearchPlan and want to skip LLM parsing."
    ),
)
async def execute_search_plan(
    request: DirectSearchPlanRequest,
) -> CandidateSearchResponse:
    """
    Executes a pre-built SearchPlan directly, bypassing the LLM requirement parser.
    """
    global _latest_search_plan, _latest_plan_timestamp

    plan = request.plan

    # Ensure defaults
    if not plan.active_in:
        plan.active_in = "15 days"
    if not plan.candidate_display:
        plan.candidate_display = "All candidates"
    if plan.verified_mobile is None:
        plan.verified_mobile = True
    if plan.verified_email is None:
        plan.verified_email = True
    if plan.attached_resume is None:
        plan.attached_resume = True
    if plan.keywords and plan.keywords.required:
        plan.keywords.mandatory = True

    execution_result = ExecutionResult(
        requested=request.execute,
        executed=False,
        form_filled=False,
        search_submitted=False,
        fields_interacted=[],
        message="Dry-run mode: SearchPlan executed without Selenium.",
    )

    if request.execute:
        portal = NaukriResdexPortal()
        execution_result = portal.execute_plan(
            plan=plan,
            submit_search=request.submit_search,
        )

    _latest_search_plan = plan.model_dump()
    _latest_plan_timestamp = time.time()

    return CandidateSearchResponse(
        requirement="(direct SearchPlan)",
        search_plan=plan,
        validation=ValidationResult(valid=True, errors=[], warnings=[]),
        execution=execution_result,
    )


@router.post(
    "/upload-requirement",
    status_code=status.HTTP_200_OK,
    summary="Extract text from Requirement Document / PDF",
    description="Extracts raw, structured requirement text from uploaded PDF, DOCX, DOC, or TXT document preserving all formatting.",
)
async def upload_requirement_document(
    file: UploadFile = File(..., description="Requirement or Job Description document (PDF, DOCX, DOC, TXT)"),
):
    """Extracts text from an uploaded requirement document."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_DOC_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Allowed formats: {', '.join(sorted(ALLOWED_DOC_EXTENSIONS))}",
        )

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File exceeds maximum allowed size of 10 MB.")

    extracted_text = ""
    try:
        if ext == ".pdf":
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page_texts = []
            for page in doc:
                text = page.get_text()
                if text.strip():
                    page_texts.append(text)
            extracted_text = "\n\n".join(page_texts).strip()

        elif ext == ".docx":
            doc_stream = io.BytesIO(file_bytes)
            docx_doc = docx.Document(doc_stream)
            paragraphs = [p.text for p in docx_doc.paragraphs if p.text.strip()]
            
            # Also extract table text if present
            table_lines = []
            for table in docx_doc.tables:
                for row in table.rows:
                    cells = [c.text.strip() for c in row.cells if c.text.strip()]
                    if cells:
                        table_lines.append(" | ".join(cells))
            
            extracted_text = "\n".join(paragraphs)
            if table_lines:
                extracted_text += "\n\n" + "\n".join(table_lines)

        elif ext == ".txt":
            try:
                extracted_text = file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                extracted_text = file_bytes.decode("latin-1", errors="replace")

        elif ext == ".doc":
            # Extract plain text characters from legacy .doc binary
            text_chars = re.findall(rb"[\x20-\x7E\r\n\t]{4,}", file_bytes)
            extracted_text = "\n".join(tc.decode("latin-1", errors="ignore") for tc in text_chars)

    except Exception as exc:
        logger.error(f"Failed to extract requirement text from {file.filename}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read requirement document: {str(exc)}",
        )

    if not extracted_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not extract readable text from the document. Please ensure it is not an empty or scanned image file.",
        )

    return {
        "status": "success",
        "filename": file.filename,
        "size": len(file_bytes),
        "extracted_text": extracted_text.strip(),
        "char_count": len(extracted_text.strip()),
        "line_count": len(extracted_text.strip().splitlines()),
    }
