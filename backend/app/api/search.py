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
from app.services.requirement_service import RequirementService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["Candidate Search"])

requirement_service = RequirementService()

ALLOWED_DOC_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


_latest_search_plan = None
_latest_plan_timestamp = 0.0


@router.get(
    "/active-plan",
    summary="Get active SearchPlan for Naukri Resdex browser auto-fill",
)
async def get_active_plan():
    """Returns the latest SearchPlan for the extension to auto-fill."""
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
    summary="Generate SearchPlan from natural language requirement",
)
async def search_candidates(
    request: CandidateSearchRequest,
) -> CandidateSearchResponse:
    """
    Parses natural language requirement into structured SearchPlan.
    Plan is stored for the extension to pick up.
    """
    global _latest_search_plan, _latest_plan_timestamp

    plan, validation = requirement_service.process_requirement(request.requirement)

    if request.active_in:
        plan.active_in = request.active_in
    if request.verified_mobile is not None:
        plan.verified_mobile = request.verified_mobile
    if request.verified_email is not None:
        plan.verified_email = request.verified_email
    if request.attached_resume is not None:
        plan.attached_resume = request.attached_resume

    _latest_search_plan = plan.model_dump()
    _latest_plan_timestamp = time.time()

    execution_result = ExecutionResult(
        requested=False,
        executed=False,
        form_filled=False,
        search_submitted=False,
        fields_interacted=[],
        message="SearchPlan generated. Extension will auto-fill the form.",
    )

    return CandidateSearchResponse(
        requirement=request.requirement,
        search_plan=plan,
        validation=validation,
        execution=execution_result,
    )


class DirectSearchPlanRequest(BaseModel):
    plan: SearchPlan = Field(..., description="Pre-built SearchPlan to store for extension")


@router.post(
    "/plan",
    response_model=CandidateSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Store a pre-built SearchPlan for extension",
)
async def store_search_plan(
    request: DirectSearchPlanRequest,
) -> CandidateSearchResponse:
    """Stores a pre-built SearchPlan for the extension to pick up."""
    global _latest_search_plan, _latest_plan_timestamp

    plan = request.plan

    _latest_search_plan = plan.model_dump()
    _latest_plan_timestamp = time.time()

    execution_result = ExecutionResult(
        requested=False,
        executed=False,
        form_filled=False,
        search_submitted=False,
        fields_interacted=[],
        message="SearchPlan stored. Extension will auto-fill the form.",
    )

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
)
async def upload_requirement_document(
    file: UploadFile = File(..., description="Requirement or Job Description document (PDF, DOCX, DOC, TXT)"),
):
    """Extracts raw, structured requirement text from uploaded document."""
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
