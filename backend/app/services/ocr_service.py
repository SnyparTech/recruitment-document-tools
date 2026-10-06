"""
OCR Service for Image-Based / Scanned Resumes.

Handles the case where a resume is uploaded as a photo (JPG/PNG) or a scanned
PDF with no embedded text layer. Runs PaddleOCR (PP-OCRv4 — lighter and more
accurate than Tesseract on real-world document layouts, still CPU-friendly)
to produce:
1. A text-searchable PDF (image + invisible text layer positioned at each
   detected line's bounding box), so the candidate's original document stays
   visually intact but becomes copy/paste-able.
2. Plain extracted text, fed into the same canonical-content shape the rest
   of the pipeline (DLP masking, AI structuring) already expects.
"""

import io
import logging
from typing import Any, Dict, List, Tuple

import fitz  # PyMuPDF
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Below this many non-whitespace characters, a "text" PDF is treated as a
# scanned image with no usable text layer.
SCANNED_PDF_TEXT_THRESHOLD = 40


class OCRUnavailableError(Exception):
    """Raised when the PaddleOCR engine/models are not installed/reachable."""


def needs_ocr(detected_type: str, canonical_content: Dict[str, Any]) -> bool:
    """True if the upload is an image, or a PDF whose extracted text is too
    sparse to be a real text layer (i.e. it's a scanned/photographed page)."""
    if detected_type == "image":
        return True
    if detected_type == "pdf":
        raw_text = (canonical_content.get("raw_text") or "").strip()
        return len(raw_text) < SCANNED_PDF_TEXT_THRESHOLD
    return False


# Loading PaddleOCR's models takes real time (seconds) — do it once per
# process, not per request/page.
_engine = None


def _get_engine():
    global _engine
    if _engine is not None:
        return _engine
    try:
        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise OCRUnavailableError("OCR engine (PaddleOCR) is not installed on the server.") from exc

    try:
        _engine = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
    except Exception as exc:
        raise OCRUnavailableError(f"Could not initialize PaddleOCR: {exc}") from exc
    return _engine


def _ocr_image_to_pdf_page(image: "Image.Image") -> Tuple[bytes, str]:
    """OCRs a single PIL image, returning (single-page searchable PDF bytes, extracted text)."""
    engine = _get_engine()

    img_array = np.array(image)
    try:
        raw_result = engine.ocr(img_array, cls=True)
    except Exception as exc:
        raise OCRUnavailableError(f"PaddleOCR failed on this page: {exc}") from exc

    # PaddleOCR returns a list-per-image; for a single image that's
    # raw_result[0] (or None if nothing detected).
    lines: List[Tuple[List[List[float]], str]] = []
    page_lines = raw_result[0] if raw_result else None
    if page_lines:
        for box, (text, _confidence) in page_lines:
            if text and text.strip():
                lines.append((box, text.strip()))

    doc = fitz.open()
    page = doc.new_page(width=image.width, height=image.height)

    img_bytes_io = io.BytesIO()
    image.convert("RGB").save(img_bytes_io, format="PNG")
    page.insert_image(fitz.Rect(0, 0, image.width, image.height), stream=img_bytes_io.getvalue())

    text_parts = []
    for box, text in lines:
        text_parts.append(text)
        top_left = box[0]
        bottom_left = box[3]
        line_height = max(abs(bottom_left[1] - top_left[1]), 6)
        fontsize = max(line_height * 0.75, 4)
        try:
            # render_mode=3 = invisible text, same trick Tesseract's
            # searchable-PDF output uses — keeps the page looking like the
            # original photo while making the text selectable/copyable.
            page.insert_text(
                (top_left[0], top_left[1] + line_height * 0.85),
                text,
                fontsize=fontsize,
                render_mode=3,
            )
        except Exception as exc:
            logger.warning("Could not place invisible OCR text for a line (%s) — text still included in raw_text.", exc)

    pdf_bytes = doc.tobytes()
    doc.close()

    return pdf_bytes, "\n".join(text_parts)


def run_ocr(file_path: str, detected_type: str) -> Dict[str, Any]:
    """
    Runs OCR on an image or scanned PDF and returns:
    {
        "searchable_pdf_bytes": bytes,
        "raw_text": str,
    }
    """
    page_pdfs = []
    text_parts = []

    if detected_type == "image":
        image = Image.open(file_path)
        if image.mode != "RGB":
            image = image.convert("RGB")
        pdf_bytes, text = _ocr_image_to_pdf_page(image)
        page_pdfs.append(pdf_bytes)
        text_parts.append(text)

    elif detected_type == "pdf":
        src = fitz.open(file_path)
        try:
            for page_idx in range(len(src)):
                page = src[page_idx]
                # Render at 2x for reasonable OCR accuracy on small resume text.
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                image = Image.open(io.BytesIO(pix.tobytes("png")))
                pdf_bytes, text = _ocr_image_to_pdf_page(image)
                page_pdfs.append(pdf_bytes)
                text_parts.append(text)
        finally:
            src.close()
    else:
        raise ValueError(f"OCR not supported for detected_type: {detected_type}")

    merged = fitz.open()
    for pdf_bytes in page_pdfs:
        with fitz.open("pdf", pdf_bytes) as page_doc:
            merged.insert_pdf(page_doc)
    searchable_pdf_bytes = merged.tobytes()
    merged.close()

    return {
        "searchable_pdf_bytes": searchable_pdf_bytes,
        "raw_text": "\n\n".join(t.strip() for t in text_parts if t.strip()).strip(),
    }
