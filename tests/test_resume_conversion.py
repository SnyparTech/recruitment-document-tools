"""
Unit & Integration Test Suite for Resume Upload & AI Conversion Pipeline.
"""

import os
import sys

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import pytest
from app.core.file_validator import FileValidationError, FileValidator
from app.services.ai_providers import DeterministicFallbackParser, GroqResumeAIProvider
from app.services.completeness_validator import CompletenessValidator
from app.services.dlp_service import DLPService
from app.services.docx_resume_generator import DocxResumeGenerator
from app.services.latex_generator import LatexResumeGenerator
from app.services.resume_extractor import ResumeExtractor


def test_file_validation_rejects_disguised_executable():
    """Verifies that an executable renamed as a PDF is strictly rejected."""
    fake_exe_bytes = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00" + b"A" * 100
    with pytest.raises(FileValidationError) as excinfo:
        FileValidator.validate_upload("malicious.pdf", fake_exe_bytes, "application/pdf")
    assert "content does not match" in str(excinfo.value)


def test_file_validation_rejects_oversized_file():
    """Verifies that files > 10MB are rejected with clear error."""
    oversized_bytes = b"A" * (10 * 1024 * 1024 + 10)
    with pytest.raises(FileValidationError) as excinfo:
        FileValidator.validate_upload("huge_resume.pdf", oversized_bytes, "application/pdf")
    assert "File is too large" in str(excinfo.value)


def test_file_validation_accepts_valid_pdf():
    """Verifies that legitimate PDF magic bytes pass validation."""
    valid_pdf_bytes = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
    ext, detected = FileValidator.validate_upload("sample.pdf", valid_pdf_bytes, "application/pdf")
    assert ext == ".pdf"
    assert detected == "pdf"


def test_dlp_aadhaar_masking_all_formats():
    """Verifies Aadhaar detection in standard, spaced, and hyphenated formats."""
    text = (
        "Candidate Aadhaar: 1234 5678 9012, alternate: 9876-5432-1098, "
        "continuous: 234567890123. PAN: ABCDE1234F."
    )
    res = DLPService.sanitize_resume_text(text)
    assert "1234 XXXX 9012" in res.sanitized_text
    assert "9876 XXXX 1098" in res.sanitized_text
    assert "2345 XXXX 0123" in res.sanitized_text
    assert "ABCDE****F" in res.sanitized_text
    assert res.detected_count >= 4


def test_latex_generation_and_escaping():
    """Verifies that LaTeX generation properly escapes special chars and generates template sections."""
    sample_data = {
        "personal_information": {
            "name": "Jane Doe & Associates",
            "phone": "+1 555-0199",
            "location": "New York, NY",
            "email": "jane@example.com",
            "linkedin": "linkedin.com/in/janedoe",
            "website": "https://example.com/resume?user=1&test=true",
        },
        "objective": "Targeting 100% efficiency & 50% cost reduction.",
        "education": [
            {
                "degree": "B.S. in Computer Science",
                "institution": "MIT #1",
                "location": "Cambridge, MA",
                "date": "2018 - 2022",
                "details": ["GPA: 3.9/4.0 (Top 5%)"],
            }
        ],
        "skills": {
            "technical_skills": ["Python & C++", "FastAPI_framework", "AWS (100% cloud)"],
            "soft_skills": ["Team Leadership"],
            "additional_skills": ["Docker", "Kubernetes"],
        },
        "experience": [
            {
                "role": "Senior Engineer",
                "company": "Tech Corp & Co.",
                "location": "Boston, MA",
                "start_date": "2022",
                "end_date": "Present",
                "bullets": [
                    "Improved latency by 35% across 10M+ daily requests.",
                    "Handled $2.5M in infrastructure budget with 99.99% uptime.",
                ],
            }
        ],
        "projects": [
            {
                "title": "AI Resume Engine",
                "description": "Zero-data-loss compiler with LaTeX & DOCX output.",
                "url": "https://github.com/test/repo",
            }
        ],
        "extra_curricular_activities": ["Hackathon Winner 2023"],
        "leadership": ["Club President"],
        "additional_sections": [
            {
                "title": "CERTIFICATIONS",
                "items": ["AWS Certified Solutions Architect", "CKA - Kubernetes"],
            }
        ],
    }

    latex = LatexResumeGenerator.generate_latex(sample_data)
    assert r"\documentclass{resume}" in latex
    assert r"\name{Jane Doe \& Associates}" in latex
    assert r"100\% efficiency" in latex
    assert r"Python \& C++" in latex
    assert r"\begin{rSection}{CERTIFICATIONS}" in latex
    assert "AWS Certified Solutions Architect" in latex


def test_docx_generation_output(tmp_path):
    """Verifies that the DOCX file is successfully generated with proper formatting."""
    sample_data = {
        "personal_information": {
            "name": "Jane Doe",
            "phone": "+1 555-0199",
            "location": "New York, NY",
            "email": "jane@example.com",
            "linkedin": "linkedin.com/in/janedoe",
            "website": "https://example.com",
        },
        "objective": "Driven software engineer.",
        "skills": {
            "technical_skills": ["Python", "FastAPI", "React"],
        },
        "experience": [
            {
                "role": "Software Engineer",
                "company": "Acme Inc.",
                "location": "NY",
                "start_date": "2021",
                "end_date": "Present",
                "bullets": ["Engineered core backend pipelines."],
            }
        ],
    }

    out_file = str(tmp_path / "test_resume.docx")
    DocxResumeGenerator.generate_docx(sample_data, out_file)
    assert os.path.exists(out_file)
    assert os.path.getsize(out_file) > 1000


if __name__ == "__main__":
    test_file_validation_rejects_disguised_executable()
    test_file_validation_rejects_oversized_file()
    test_file_validation_accepts_valid_pdf()
    test_dlp_aadhaar_masking_all_formats()
    test_latex_generation_and_escaping()
    print("All tests passed successfully!")
