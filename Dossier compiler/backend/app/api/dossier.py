"""
Dossier API Endpoints.

Handles multipart upload of:
1. Photo (image/jpeg, image/png, image/webp)
2. Identity Proof (application/pdf, image/jpeg, image/png)
3. Resume (application/pdf, application/vnd.openxmlformats-officedocument.wordprocessingml.document, text/plain)

Compiles these files into a professional DOCX candidate dossier and provides
download capabilities.
"""

import logging
import os
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from app.services.dossier_service import DossierService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dossier", tags=["Candidate Dossier Compiler"])
dossier_service = DossierService()

# In-memory dossier registry for fast retrieval of metadata
DOSSIER_REGISTRY = {}

ALLOWED_PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_ID_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
ALLOWED_RESUME_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}


class DossierCompileResponse(BaseModel):
    """Response returned when a candidate dossier is successfully compiled."""

    dossier_id: str = Field(..., description="Unique reference ID of the compiled dossier")
    candidate_name: str = Field(..., description="Candidate name extracted or specified")
    title: str = Field(..., description="Candidate primary professional title")
    email: Optional[str] = Field(None, description="Extracted candidate email")
    phone: Optional[str] = Field(None, description="Extracted candidate phone")
    skills: list[str] = Field(default_factory=list, description="Extracted technical skills")
    id_type: str = Field(..., description="Identified ID document type")
    id_verified: bool = Field(True, description="Identity proof verification status")
    download_url: str = Field(..., description="Relative API URL to download the compiled DOCX")
    compilation_timestamp: str = Field(..., description="Date and time when dossier was compiled")
    summary: str = Field(..., description="Extracted executive summary")


@router.post(
    "/compile",
    response_model=DossierCompileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Photo, ID Proof, and Resume to Compile DOCX Dossier",
    description=(
        "Retrieves the candidate's Photo, Identity Proof, and Resume.\n"
        "1. Extracts structured resume text, competencies, and work experience.\n"
        "2. Identifies and verifies the Identity Proof document.\n"
        "3. Standardizes and embeds the Candidate Photo.\n"
        "4. Compiles all information into a professional, styled DOCX Candidate Dossier."
    ),
)
async def compile_candidate_dossier(
    photo: UploadFile = File(..., description="Candidate Portrait Photo (JPG, PNG)"),
    id_proof: UploadFile = File(..., description="Official Identity Proof (PDF, JPG, PNG)"),
    resume: UploadFile = File(..., description="Candidate Resume (PDF, DOCX, TXT)"),
    candidate_name: Optional[str] = Form(None, description="Optional candidate name override"),
    recruiter_notes: Optional[str] = Form(None, description="Optional recruiter notes to include in dossier"),
) -> DossierCompileResponse:
    """Compiles Photo, Identity Proof, and Resume into a professional DOCX dossier."""

    # 1. Validate file presence and extensions
    photo_ext = os.path.splitext(photo.filename or "")[1].lower()
    if photo_ext not in ALLOWED_PHOTO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid photo format '{photo_ext}'. Allowed formats: {', '.join(ALLOWED_PHOTO_EXTENSIONS)}",
        )

    id_ext = os.path.splitext(id_proof.filename or "")[1].lower()
    if id_ext not in ALLOWED_ID_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid identity proof format '{id_ext}'. Allowed formats: {', '.join(ALLOWED_ID_EXTENSIONS)}",
        )

    resume_ext = os.path.splitext(resume.filename or "")[1].lower()
    if resume_ext not in ALLOWED_RESUME_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid resume format '{resume_ext}'. Allowed formats: {', '.join(ALLOWED_RESUME_EXTENSIONS)}",
        )

    # 2. Read file contents into memory safely
    photo_bytes = await photo.read()
    id_bytes = await id_proof.read()
    resume_bytes = await resume.read()

    if len(photo_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded photo is empty.")
    if len(id_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded identity proof is empty.")
    if len(resume_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded resume is empty.")

    # 3. Extract text & metadata from resume
    resume_text = dossier_service.extract_resume_text(resume_bytes, resume.filename or "resume.pdf")

    # 4. Analyze identity proof
    id_type, id_num = dossier_service.analyze_identity_proof(id_bytes, id_proof.filename or "id.pdf")

    # 5. Parse candidate profile
    profile = dossier_service.parse_profile_from_resume(resume_text, candidate_name=candidate_name)
    profile.id_type = id_type
    profile.id_number = id_num

    # 6. Generate DOCX Dossier with EXACT embedded documents
    dossier_id, file_path = dossier_service.compile_dossier_docx(
        profile=profile,
        photo_bytes=photo_bytes,
        photo_filename=photo.filename or "Candidate_Photo.jpg",
        id_proof_bytes=id_bytes,
        id_proof_filename=id_proof.filename or "Identity_Proof.pdf",
        resume_bytes=resume_bytes,
        resume_filename=resume.filename or "Resume.pdf",
        recruiter_notes=recruiter_notes,
    )

    # 7. Record in registry
    DOSSIER_REGISTRY[dossier_id] = {
        "dossier_id": dossier_id,
        "file_path": file_path,
        "filename": os.path.basename(file_path),
        "profile": profile,
    }

    return DossierCompileResponse(
        dossier_id=dossier_id,
        candidate_name=profile.name,
        title=profile.title,
        email=profile.email,
        phone=profile.phone,
        skills=profile.skills,
        id_type=profile.id_type,
        id_verified=profile.id_verified,
        download_url=f"/dossier/download/{dossier_id}",
        compilation_timestamp=profile.compilation_timestamp,
        summary=profile.summary,
    )


@router.get(
    "/download/{dossier_id}",
    summary="Download Compiled DOCX Candidate Dossier",
    description="Streams the compiled .docx document as an attachment download.",
)
async def download_dossier(dossier_id: str):
    """Downloads the compiled DOCX file for a given dossier_id."""
    record = DOSSIER_REGISTRY.get(dossier_id)
    if not record:
        # Check on disk
        for fname in os.listdir(dossier_service.storage_dir):
            if dossier_id in fname and fname.endswith(".docx"):
                file_path = os.path.join(dossier_service.storage_dir, fname)
                return FileResponse(
                    path=file_path,
                    filename=fname,
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dossier with ID '{dossier_id}' not found.",
        )

    file_path = record["file_path"]
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Dossier file missing on server disk.")

    return FileResponse(
        path=file_path,
        filename=record["filename"],
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@router.get(
    "/{dossier_id}",
    summary="Get Extracted Dossier Profile Metadata",
)
async def get_dossier_metadata(dossier_id: str):
    """Returns metadata for an existing dossier."""
    record = DOSSIER_REGISTRY.get(dossier_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dossier with ID '{dossier_id}' not found.",
        )
    return {
        "dossier_id": dossier_id,
        "filename": record["filename"],
        "download_url": f"/dossier/download/{dossier_id}",
    }
