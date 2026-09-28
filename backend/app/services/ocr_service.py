"""
OCR Service for Image-Based / Scanned Resumes.

Handles the case where a resume is uploaded as a photo (JPG/PNG) or a scanned
PDF with no embedded text layer. Runs Tesseract OCR to produce:
1. A text-searchable PDF (image + invisible text layer), so the candidate's
   original document remains visually intact but becomes copy/paste-able.
2. Plain extracted text, fed into the same canonical-content shape the rest
   of the pipeline (DLP masking, AI structuring) already expects.
"""

import io
import logging
from typing import Any, Dict, Tuple

import fitz  # PyMuPDF
from PIL import Image

logger = logging.getLogger(__name__)

# Below this many non-whitespace characters, a "text" PDF is treated as a
# scanned image with no usable text layer.
SCANNED_PDF_TEXT_THRESHOLD = 40


class OCRUnavailableError(Exception):
    """Raised when the Tesseract OCR engine is not installed/reachable."""


def needs_ocr(detected_type: str, canonical_content: Dict[str, Any]) -> bool:
    """True if the upload is an image, or a PDF whose extracted text is too
    sparse to be a real text layer (i.e. it's a scanned/photographed page)."""
    if detected_type == "image":
        return True
    if detected_type == "pdf":
        raw_text = (canonical_content.get("raw_text") or "").strip()
        return len(raw_text) < SCANNED_PDF_TEXT_THRESHOLD
    return False


def _ocr_image_to_pdf_page(image: "Image.Image") -> Tuple[bytes, str]:
    """OCRs a single PIL image, returning (single-page searchable PDF bytes, extracted text)."""
    import pytesseract

    try:
        pdf_bytes = pytesseract.image_to_pdf_or_hocr(image, extension="pdf")
        text = pytesseract.image_to_string(image)
    except pytesseract.TesseractNotFoundError as exc:
        raise OCRUnavailableError(
            "OCR engine (Tesseract) is not installed on the server."
        ) from exc
    return pdf_bytes, text


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
