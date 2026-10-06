"""
Tests for ocr_service's PaddleOCR integration (searchable-PDF construction,
needs_ocr detection). PaddleOCR itself isn't installed in this test
environment (heavy model download) — _get_engine() is stubbed with a fake
engine whose .ocr() returns PaddleOCR's real result shape
(list-per-image -> list of [box, (text, confidence)]), so these tests cover
our own box-placement/text-joining logic, not PaddleOCR's internals.
"""
import io
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import fitz
from PIL import Image

from app.services import ocr_service


class _FakeEngine:
    def __init__(self, lines):
        self._lines = lines

    def ocr(self, img_array, cls=True):
        return [self._lines]


def _blank_image(w=200, h=100):
    return Image.new("RGB", (w, h), color="white")


def test_needs_ocr_true_for_images_always():
    assert ocr_service.needs_ocr("image", {}) is True


def test_needs_ocr_true_for_sparse_pdf_text():
    assert ocr_service.needs_ocr("pdf", {"raw_text": "  "}) is True


def test_needs_ocr_false_for_pdf_with_real_text_layer():
    assert ocr_service.needs_ocr("pdf", {"raw_text": "A" * 100}) is False


def test_get_engine_raises_ocr_unavailable_when_paddleocr_not_installed(monkeypatch):
    monkeypatch.setattr(ocr_service, "_engine", None)
    try:
        ocr_service._get_engine()
        assert False, "expected OCRUnavailableError"
    except ocr_service.OCRUnavailableError as exc:
        assert "PaddleOCR" in str(exc)


def test_ocr_image_to_pdf_page_builds_text_and_searchable_pdf(monkeypatch):
    fake_lines = [
        ([[10, 10], [100, 10], [100, 30], [10, 30]], ("John Doe", 0.98)),
        ([[10, 40], [150, 40], [150, 60], [10, 60]], ("Senior Python Developer", 0.95)),
    ]
    monkeypatch.setattr(ocr_service, "_get_engine", lambda: _FakeEngine(fake_lines))

    pdf_bytes, text = ocr_service._ocr_image_to_pdf_page(_blank_image())

    assert text == "John Doe\nSenior Python Developer"
    doc = fitz.open("pdf", pdf_bytes)
    assert len(doc) == 1
    # The invisible text layer must make the page's extracted text match what PaddleOCR saw.
    extracted = doc[0].get_text()
    assert "John Doe" in extracted
    assert "Senior Python Developer" in extracted
    doc.close()


def test_ocr_image_to_pdf_page_handles_no_text_detected(monkeypatch):
    monkeypatch.setattr(ocr_service, "_get_engine", lambda: _FakeEngine([]))
    pdf_bytes, text = ocr_service._ocr_image_to_pdf_page(_blank_image())
    assert text == ""
    doc = fitz.open("pdf", pdf_bytes)
    assert len(doc) == 1
    doc.close()


def test_run_ocr_image_returns_searchable_pdf_and_raw_text(monkeypatch, tmp_path):
    fake_lines = [([[5, 5], [80, 5], [80, 20], [5, 20]], ("Ravi Kumar", 0.99))]
    monkeypatch.setattr(ocr_service, "_get_engine", lambda: _FakeEngine(fake_lines))

    img_path = tmp_path / "resume.png"
    _blank_image().save(img_path)

    result = ocr_service.run_ocr(str(img_path), "image")
    assert result["raw_text"] == "Ravi Kumar"
    assert result["searchable_pdf_bytes"].startswith(b"%PDF")


def test_run_ocr_pdf_merges_all_pages(monkeypatch, tmp_path):
    fake_lines = [([[5, 5], [80, 5], [80, 20], [5, 20]], ("Page Text", 0.99))]
    monkeypatch.setattr(ocr_service, "_get_engine", lambda: _FakeEngine(fake_lines))

    src = fitz.open()
    src.new_page(width=200, height=100)
    src.new_page(width=200, height=100)
    pdf_path = tmp_path / "scanned.pdf"
    src.save(str(pdf_path))
    src.close()

    result = ocr_service.run_ocr(str(pdf_path), "pdf")
    doc = fitz.open("pdf", result["searchable_pdf_bytes"])
    assert len(doc) == 2
    doc.close()
    assert result["raw_text"].count("Page Text") == 2
