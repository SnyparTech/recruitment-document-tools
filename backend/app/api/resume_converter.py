"""
Resume Upload and AI Resume Conversion API Router.

Endpoints:
- POST /api/resume/upload: Validates file, scans security & magic bytes, DLP masks sensitive data, extracts canonical content.
- POST /api/resume/convert: Runs LLM structuring with zero-loss guarantee, audits completeness, compiles LaTeX, DOCX, and PDF.
- GET  /api/resume/download/{task_id}/{file_type}: Secure download endpoint for .docx, .pdf, or .tex.
- GET  /api/resume/preview/{task_id}: Returns preview details (LaTeX source, JSON, audit score).
"""

import json
import logging
import os
import time
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from app.core.file_validator import (
    FileValidationError,
    FileValidator,
    MAX_RESUME_SIZE_BYTES,
)
from app.services.ai_providers import GroqResumeAIProvider
from app.services.completeness_validator import CompletenessValidator
from app.services.dlp_service import DLPService
from app.services.docx_resume_generator import DocxResumeGenerator
from app.services.latex_generator import LatexResumeGenerator
from app.services.resume_extractor import ResumeExtractor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/resume", tags=["AI Resume Converter"])

# Base directories for temporary storage
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
UPLOADS_DIR = os.path.join(BASE_DIR, "storage", "resume_uploads")
OUTPUTS_DIR = os.path.join(BASE_DIR, "storage", "resume_outputs")
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(OUTPUTS_DIR, exist_ok=True)

# In-memory session stores with creation timestamps
upload_sessions: Dict[str, Dict[str, Any]] = {}
conversion_tasks: Dict[str, Dict[str, Any]] = {}

SESSION_TTL_SECONDS = 3600  # 1 hour retention


def cleanup_expired_sessions():
    """Purges sessions older than 1 hour."""
    now = time.time()
    expired_uploads = [
        k for k, v in upload_sessions.items() if now - v.get("timestamp", 0) > SESSION_TTL_SECONDS
    ]
    for k in expired_uploads:
        sess = upload_sessions.pop(k, None)
        if sess and os.path.exists(sess.get("file_path", "")):
            try:
                os.remove(sess["file_path"])
            except Exception:
                pass

    expired_tasks = [
        k for k, v in conversion_tasks.items() if now - v.get("timestamp", 0) > SESSION_TTL_SECONDS
    ]
    for k in expired_tasks:
        conversion_tasks.pop(k, None)


class ConvertResumeRequest(BaseModel):
    upload_id: str
    model: Optional[str] = None


@router.post("/upload", summary="Upload & Validate Resume with Security & DLP")
async def upload_resume(file: UploadFile = File(...)):
    """
    Validates uploaded resume (PDF, DOC, DOCX), verifies magic bytes, protects against
    zip bombs and malware, runs DLP sensitive data masking, and deterministically extracts content.
    """
    cleanup_expired_sessions()

    if not file or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "NO_FILE", "message": "No file uploaded."},
        )

    try:
        content_bytes = await file.read()
    except Exception as e:
        logger.error(f"Failed to read upload stream: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "READ_ERROR", "message": "Failed to read uploaded file."},
        )

    # 1. Security & Magic Byte Validation
    try:
        ext, detected_type = FileValidator.validate_upload(
            filename=file.filename,
            content_bytes=content_bytes,
            content_type=file.content_type,
            max_size_bytes=MAX_RESUME_SIZE_BYTES,
        )
    except FileValidationError as ve:
        logger.warning(f"File validation rejected '{file.filename}': {ve.message}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": ve.code, "message": ve.message},
        )

    # 2. Store securely outside publicly executable paths with random UUID
    upload_id, file_path = FileValidator.generate_secure_storage_path(UPLOADS_DIR, ext)
    with open(file_path, "wb") as f:
        f.write(content_bytes)

    # 3. Deterministic Content Extraction
    try:
        canonical_content = ResumeExtractor.extract(file_path, detected_type)
    except Exception as exc:
        logger.error(f"Resume extraction failure: {exc}")
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "EXTRACTION_FAILED",
                "message": "Failed to extract readable content from the document.",
            },
        )

    # 4. DLP and Sensitive Data Masking (Aadhaar, PAN, Cards, Passports, Bank Accounts)
    raw_text = canonical_content.get("raw_text", "")
    dlp_result = DLPService.sanitize_resume_text(raw_text)

    # Save session state
    upload_sessions[upload_id] = {
        "upload_id": upload_id,
        "original_filename": file.filename,
        "file_path": file_path,
        "detected_type": detected_type,
        "file_size": len(content_bytes),
        "canonical_content": canonical_content,
        "sanitized_text": dlp_result.sanitized_text,
        "dlp_result": dlp_result,
        "timestamp": time.time(),
    }

    # Prepare preview snippet
    lines = [l.strip() for l in dlp_result.sanitized_text.splitlines() if l.strip()]
    snippet = "\n".join(lines[:12]) if lines else "Document extracted successfully."
    section_titles = [s.get("title", "") for s in canonical_content.get("sections", [])]

    return {
        "status": "success",
        "upload_id": upload_id,
        "filename": file.filename,
        "detected_type": detected_type.upper(),
        "file_size_bytes": len(content_bytes),
        "dlp_summary": dlp_result.to_dict(),
        "preview_snippet": snippet,
        "sections_detected": section_titles,
        "message": "File validated and sanitized successfully. Ready for AI conversion.",
    }


@router.post("/convert", summary="Structure Resume with LLM & Generate LaTeX/DOCX")
async def convert_resume(req: ConvertResumeRequest):
    """
    Executes the 10-step resume conversion pipeline:
    LLM structuring -> completeness verification -> LaTeX compilation -> DOCX generation.
    """
    cleanup_expired_sessions()

    session = upload_sessions.get(req.upload_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "SESSION_EXPIRED", "message": "Upload session expired or not found. Please upload again."},
        )

    canonical_content = session["canonical_content"]
    sanitized_text = session["sanitized_text"]
    orig_filename = session["original_filename"]

    # 1. AI Structuring via Groq Provider (or deterministic local fallback)
    provider = GroqResumeAIProvider(model=req.model)
    try:
        structured_json = await provider.structure_resume(canonical_content, sanitized_text)
    except Exception as exc:
        logger.error(f"AI structuring error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "AI_STRUCTURING_FAILED", "message": "Failed to structure resume content with AI."},
        )

    # 2. Information Completeness Validation & Zero-Loss Repair Loop
    canonical_bullets = canonical_content.get("bullets", [])
    repaired_resume, audit_report = CompletenessValidator.validate_and_repair(
        original_text=sanitized_text,
        structured_resume=structured_json,
        canonical_bullets=canonical_bullets,
    )

    # 3. Generate LaTeX Document Code
    try:
        latex_code = LatexResumeGenerator.generate_latex(repaired_resume)
    except Exception as exc:
        logger.error(f"LaTeX generation failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "LATEX_GENERATION_FAILED", "message": "Failed to map content into LaTeX template."},
        )

    # 4. Generate DOCX File
    task_id = uuid.uuid4().hex
    task_dir = os.path.join(OUTPUTS_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)

    candidate_name = repaired_resume.get("personal_information", {}).get("name") or "Candidate"
    safe_base_name = "".join(c for c in candidate_name if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
    if not safe_base_name:
        safe_base_name = "Resume"

    docx_filename = f"{safe_base_name}_Resume.docx"
    docx_path = os.path.join(task_dir, docx_filename)

    try:
        DocxResumeGenerator.generate_docx(repaired_resume, docx_path)
    except Exception as exc:
        logger.error(f"DOCX generation failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "DOCX_GENERATION_FAILED", "message": "Failed to compile editable DOCX resume."},
        )

    # 5. Save LaTeX Source (.tex)
    tex_filename = f"{safe_base_name}_Resume.tex"
    tex_path = os.path.join(task_dir, tex_filename)
    with open(tex_path, "w", encoding="utf-8") as f_tex:
        f_tex.write(latex_code)

    # 6. Companion PDF Generation via Word COM
    pdf_filename = f"{safe_base_name}_Resume.pdf"
    pdf_path = os.path.join(task_dir, pdf_filename)
    has_pdf = False
    try:
        pdf_res = DocxResumeGenerator.convert_docx_to_pdf(docx_path, pdf_path)
        if pdf_res and os.path.exists(pdf_path):
            has_pdf = True
    except Exception as exc:
        logger.warning(f"Companion PDF compilation skipped: {exc}")

    # Record completed task
    conversion_tasks[task_id] = {
        "task_id": task_id,
        "candidate_name": candidate_name,
        "docx_path": docx_path,
        "docx_filename": docx_filename,
        "tex_path": tex_path,
        "tex_filename": tex_filename,
        "pdf_path": pdf_path if has_pdf else None,
        "pdf_filename": pdf_filename if has_pdf else None,
        "structured_resume": repaired_resume,
        "audit_report": audit_report,
        "latex_code": latex_code,
        "timestamp": time.time(),
    }

    return {
        "status": "ready",
        "task_id": task_id,
        "candidate_name": candidate_name,
        "completeness_report": audit_report,
        "has_pdf": has_pdf,
        "download_urls": {
            "docx": f"/api/resume/download/{task_id}/docx",
            "pdf": f"/api/resume/download/{task_id}/pdf" if has_pdf else None,
            "tex": f"/api/resume/download/{task_id}/tex",
        },
        "preview_url": f"/api/resume/preview/{task_id}",
    }


@router.get("/download/{task_id}/{file_type}", summary="Download Converted Resume File")
async def download_resume_file(task_id: str, file_type: str):
    """Streams the requested file (docx, pdf, or tex) with appropriate headers."""
    task = conversion_tasks.get(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "TASK_NOT_FOUND", "message": "Conversion task not found or expired."},
        )

    file_type = file_type.lower().strip()
    if file_type == "docx":
        path = task.get("docx_path")
        filename = task.get("docx_filename", "Resume.docx")
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif file_type == "pdf":
        path = task.get("pdf_path")
        filename = task.get("pdf_filename", "Resume.pdf")
        media_type = "application/pdf"
        if not path or not os.path.exists(path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "PDF_NOT_AVAILABLE", "message": "PDF output is not available for this resume."},
            )
    elif file_type in ("tex", "latex"):
        path = task.get("tex_path")
        filename = task.get("tex_filename", "Resume.tex")
        media_type = "text/x-tex"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_TYPE", "message": f"Unsupported file type '{file_type}'."},
        )

    if not path or not os.path.exists(path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "FILE_NOT_FOUND", "message": "File not found on server."},
        )

    return FileResponse(
        path=path,
        media_type=media_type,
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/preview/{task_id}", summary="Preview Converted Resume Content & Audit Score")
async def preview_resume(task_id: str):
    """Returns structured JSON, LaTeX source, and completeness audit report."""
    task = conversion_tasks.get(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "TASK_NOT_FOUND", "message": "Conversion task not found or expired."},
        )

    return {
        "task_id": task_id,
        "candidate_name": task.get("candidate_name"),
        "structured_resume": task.get("structured_resume"),
        "audit_report": task.get("audit_report"),
        "latex_code": task.get("latex_code"),
        "has_pdf": bool(task.get("pdf_path")),
    }
