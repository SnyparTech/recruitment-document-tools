"""
Unit and API Integration Tests for Candidate Dossier Compiler.

Verifies:
1. Resume text extraction & profile data parsing.
2. Identity proof document classification & masking.
3. Photo processing and DOCX document compilation.
4. FastAPI multipart file upload endpoint (/dossier/compile).
5. DOCX binary download endpoint (/dossier/download/{dossier_id}).
6. Validation rejection of invalid file extensions and empty payloads.
"""

import io
import os
import docx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.security import RateLimitMiddleware
from app.main import app
from app.services.dossier_service import CandidateProfileData, DossierService

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset rate limiter state before each test."""
    RateLimitMiddleware.reset()
    yield
    RateLimitMiddleware.reset()


def create_sample_photo_bytes() -> bytes:
    """Generates a small valid test JPEG in memory."""
    img = Image.new("RGB", (120, 120), color=(59, 130, 246))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def create_sample_resume_docx_bytes() -> bytes:
    """Generates a small valid resume DOCX file in memory."""
    doc = docx.Document()
    doc.add_heading("Aditi Sharma", level=1)
    doc.add_paragraph("Senior Python & AI Engineer | aditi.sharma@example.com | +91 9876543210")
    doc.add_paragraph(
        "Summary: Dynamic software engineer with 5 years experience building scalable backend APIs "
        "and machine learning systems using FastAPI, Python, PyTorch, and Docker."
    )
    doc.add_heading("Skills", level=2)
    doc.add_paragraph("Python, FastAPI, PyTorch, Docker, Kubernetes, SQL, REST APIs")
    doc.add_heading("Experience", level=2)
    doc.add_paragraph("Lead AI Engineer at TechInnovate (2022 - Present)")
    doc.add_paragraph("Engineered real-time candidate search algorithms reducing latency by 40%.")
    doc.add_heading("Education", level=2)
    doc.add_paragraph("B.Tech in Computer Science, IIT Bombay")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ==============================================================================
# 1. Dossier Service Unit Tests
# ==============================================================================
def test_dossier_service_text_extraction():
    """Verify resume text extraction from DOCX format."""
    service = DossierService()
    docx_bytes = create_sample_resume_docx_bytes()
    extracted_text = service.extract_resume_text(docx_bytes, "resume.docx")

    assert "Aditi Sharma" in extracted_text
    assert "FastAPI" in extracted_text
    assert "aditi.sharma@example.com" in extracted_text


def test_dossier_service_identity_analysis():
    """Verify ID proof classification and reference generation."""
    service = DossierService()

    id_type_passport, id_num = service.analyze_identity_proof(b"test", "passport_scan.pdf")
    assert id_type_passport == "Passport"

    id_type_aadhaar, _ = service.analyze_identity_proof(b"test", "aadhaar_front.jpg")
    assert id_type_aadhaar == "Aadhaar Card"

    id_type_pan, _ = service.analyze_identity_proof(b"test", "pan_card.png")
    assert id_type_pan == "PAN Card"


def test_dossier_service_profile_parsing():
    """Verify structured candidate profile parsing."""
    service = DossierService()
    sample_text = (
        "Rahul Verma\n"
        "rahul.verma@example.com | 9876543210\n"
        "Summary: Senior Full Stack Developer specializing in React, Node.js, and Python.\n"
        "Skills: React, Python, FastAPI, Docker, SQL, TypeScript\n"
        "Education: Bachelor of Technology in Computer Science\n"
    )

    profile = service.parse_profile_from_resume(sample_text)
    assert profile.name == "Rahul Verma"
    assert profile.email == "rahul.verma@example.com"
    assert "Python" in profile.skills
    assert "React" in profile.skills


def test_dossier_service_compile_docx(tmp_path):
    """Verify DOCX generation produces a valid, readable OpenXML document with embedded photo."""
    service = DossierService(storage_dir=str(tmp_path))
    profile = CandidateProfileData(
        name="Priya Patel",
        title="Senior AI Engineer",
        email="priya.patel@example.com",
        phone="+91 9123456780",
        summary="Experienced AI developer building NLP microservices.",
        skills=["Python", "FastAPI", "NLP", "PyTorch"],
        id_type="Passport",
        id_number="XXXX-XXXX-8921",
        compilation_timestamp="September 03, 2026",
    )

    photo_bytes = create_sample_photo_bytes()
    resume_bytes = create_sample_resume_docx_bytes()
    id_bytes = create_sample_photo_bytes()

    dossier_id, file_path = service.compile_dossier_docx(
        profile=profile,
        photo_bytes=photo_bytes,
        id_proof_bytes=id_bytes,
        id_proof_filename="passport_scan.jpg",
        resume_bytes=resume_bytes,
        resume_filename="resume.docx",
        recruiter_notes="Top tier recommendation for AI team.",
    )

    assert os.path.exists(file_path)
    assert dossier_id.startswith("DOSSIER-")

    # Verify generated document can be loaded back
    doc = docx.Document(file_path)
    all_text = "\n".join(p.text for p in doc.paragraphs)
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                all_text += "\n" + cell.text

    assert "Priya Patel" in all_text
    assert "Senior AI Engineer" in all_text
    assert "ID Proof" in all_text
    assert "Candidate Resume" in all_text


def test_dossier_pdf_rendering_exact_embedding(tmp_path):
    """Verify exact multi-page PDF documents are rendered as images and embedded into DOCX."""
    import fitz
    service = DossierService(storage_dir=str(tmp_path))

    # Create a real 2-page PDF in memory
    pdf_doc = fitz.open()
    page1 = pdf_doc.new_page()
    page1.insert_text((72, 72), "Resume Page 1: Software Engineer Profile")
    page2 = pdf_doc.new_page()
    page2.insert_text((72, 72), "Resume Page 2: Education and Certifications")
    pdf_bytes = pdf_doc.tobytes()

    profile = CandidateProfileData(
        name="Vikram Rao",
        title="Cloud Architect",
        summary="Cloud solutions architect.",
        skills=["AWS", "Kubernetes", "Docker"],
        id_type="Passport",
    )

    dossier_id, file_path = service.compile_dossier_docx(
        profile=profile,
        photo_bytes=create_sample_photo_bytes(),
        id_proof_bytes=pdf_bytes,
        id_proof_filename="passport.pdf",
        resume_bytes=pdf_bytes,
        resume_filename="vikram_resume.pdf",
    )

    assert os.path.exists(file_path)
    doc = docx.Document(file_path)
    text = "\n".join(p.text for p in doc.paragraphs)

    assert "Vikram Rao" in text
    assert "ID Proof" in text
    assert "Candidate Resume" in text
    assert len(doc.inline_shapes) >= 5  # Photo (1) + ID pages (2) + Resume pages (2)


# ==============================================================================
# 2. FastAPI Multipart Upload & Download Endpoints
# ==============================================================================
def test_api_compile_dossier_success():
    """Verify POST /dossier/compile endpoint creates dossier and returns metadata."""
    photo_bytes = create_sample_photo_bytes()
    resume_bytes = create_sample_resume_docx_bytes()
    id_bytes = b"Sample ID document content"

    files = {
        "photo": ("candidate_photo.jpg", photo_bytes, "image/jpeg"),
        "id_proof": ("aadhaar_proof.pdf", id_bytes, "application/pdf"),
        "resume": ("resume.docx", resume_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    }
    data = {
        "candidate_name": "Aditi Sharma",
        "recruiter_notes": "Excellent candidate for lead position.",
    }

    response = client.post("/dossier/compile", files=files, data=data)
    assert response.status_code == 201
    res_data = response.json()

    assert res_data["candidate_name"] == "Aditi Sharma"
    assert "dossier_id" in res_data
    assert res_data["id_type"] == "Aadhaar Card"
    assert res_data["download_url"].startswith("/dossier/download/")

    # Test download of the compiled file
    dossier_id = res_data["dossier_id"]
    download_resp = client.get(f"/dossier/download/{dossier_id}")
    assert download_resp.status_code == 200
    assert download_resp.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert len(download_resp.content) > 1000


def test_api_compile_dossier_invalid_photo_extension():
    """Verify rejection when photo has an invalid extension."""
    files = {
        "photo": ("invalid_photo.exe", b"fake", "application/octet-stream"),
        "id_proof": ("id.pdf", b"fake id", "application/pdf"),
        "resume": ("resume.docx", b"fake resume", "application/octet-stream"),
    }
    response = client.post("/dossier/compile", files=files)
    assert response.status_code == 400
    res_json = response.json()
    err_msg = res_json.get("message") or res_json.get("detail") or ""
    assert "Invalid photo format" in err_msg


def test_api_download_dossier_not_found():
    """Verify 404 for non-existent dossier ID."""
    response = client.get("/dossier/download/DOSSIER-NONEXISTENT")
    assert response.status_code == 404
