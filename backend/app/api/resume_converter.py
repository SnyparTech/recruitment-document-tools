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
from app.services import ocr_service

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

    # 3. Deterministic Content Extraction (images have no text layer to extract yet —
    #    that only happens once the user opts into OCR via /api/resume/ocr)
    if detected_type == "image":
        canonical_content: Dict[str, Any] = {
            "raw_text": "",
            "sections": [],
            "metadata": {"source_type": "image"},
            "tables": [],
            "bullets": [],
        }
    else:
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

    requires_ocr = ocr_service.needs_ocr(detected_type, canonical_content)

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
        "needs_ocr": requires_ocr,
        "ocr_applied": False,
        "ocr_pdf_path": None,
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
        "needs_ocr": requires_ocr,
        "is_image": detected_type == "image",
        "message": (
            "This looks like a scanned/photographed resume with no readable text layer. "
            "Run OCR to extract text before converting."
            if requires_ocr
            else "File validated and sanitized successfully. Ready for AI conversion."
        ),
    }


@router.post("/ocr", summary="OCR an Image or Scanned-PDF Resume into a Searchable PDF")
async def ocr_resume(req: ConvertResumeRequest):
    """
    Runs Tesseract OCR on an uploaded image or scanned PDF, producing a
    text-searchable PDF and extracted text. Updates the upload session's
    canonical content so a subsequent /convert call uses the OCR'd text.
    The user decides whether to call this before /convert, or skip straight
    to /convert (e.g. for a native-text PDF that was flagged unnecessarily).
    """
    cleanup_expired_sessions()

    session = upload_sessions.get(req.upload_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "SESSION_EXPIRED", "message": "Upload session expired or not found. Please upload again."},
        )

    detected_type = session["detected_type"]
    if detected_type not in ("image", "pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "OCR_NOT_APPLICABLE", "message": "OCR only applies to image or PDF uploads."},
        )

    try:
        ocr_result = ocr_service.run_ocr(session["file_path"], detected_type)
    except ocr_service.OCRUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "OCR_UNAVAILABLE", "message": str(exc)},
        )
    except Exception as exc:
        logger.error(f"OCR failed for upload {req.upload_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "OCR_FAILED", "message": "Failed to OCR the document."},
        )

    ocr_pdf_path = os.path.join(UPLOADS_DIR, f"{req.upload_id}_ocr.pdf")
    with open(ocr_pdf_path, "wb") as f:
        f.write(ocr_result["searchable_pdf_bytes"])

    ocr_raw_text = ocr_result["raw_text"]
    sections = ResumeExtractor._partition_sections(ocr_raw_text)
    canonical_content = {
        "raw_text": ocr_raw_text,
        "sections": sections,
        "metadata": {**session["canonical_content"].get("metadata", {}), "ocr_applied": True},
        "tables": [],
        "bullets": [],
    }
    dlp_result = DLPService.sanitize_resume_text(ocr_raw_text)

    session["canonical_content"] = canonical_content
    session["sanitized_text"] = dlp_result.sanitized_text
    session["dlp_result"] = dlp_result
    session["ocr_applied"] = True
    session["ocr_pdf_path"] = ocr_pdf_path
    session["needs_ocr"] = False

    lines = [l.strip() for l in dlp_result.sanitized_text.splitlines() if l.strip()]
    snippet = "\n".join(lines[:12]) if lines else "No readable text found by OCR."

    return {
        "status": "success",
        "upload_id": req.upload_id,
        "ocr_applied": True,
        "extracted_text_length": len(ocr_raw_text),
        "preview_snippet": snippet,
        "sections_detected": [s.get("title", "") for s in sections],
        "dlp_summary": dlp_result.to_dict(),
        "searchable_pdf_url": f"/api/resume/download-ocr/{req.upload_id}",
        "message": (
            "OCR complete. Review the extracted text, then continue to AI conversion or "
            "download the searchable PDF."
            if ocr_raw_text
            else "OCR ran but found no readable text. The image quality may be too low."
        ),
    }


@router.get("/download-ocr/{upload_id}", summary="Download OCR'd Searchable PDF")
async def download_ocr_pdf(upload_id: str):
    session = upload_sessions.get(upload_id)
    if not session or not session.get("ocr_pdf_path") or not os.path.exists(session["ocr_pdf_path"]):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "OCR_PDF_NOT_FOUND", "message": "No OCR'd PDF found for this upload. Run OCR first."},
        )
    filename = os.path.splitext(session["original_filename"])[0] + "_searchable.pdf"
    return FileResponse(session["ocr_pdf_path"], media_type="application/pdf", filename=filename)


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
