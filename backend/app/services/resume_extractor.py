"""
Deterministic Resume Content Extraction Service.

Extracts complete content, layout structure, tables, bullets, headings, and metadata
from PDF, DOCX, and DOC documents to produce a canonical representation:
{
    "raw_text": "...",
    "sections": [{"title": "...", "content": "..."}],
    "metadata": {"source_type": "...", "page_count": ...},
    "tables": [...],
    "bullets": [...]
}
"""

import io
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import docx
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

# Common resume section markers for deterministic partitioning
SECTION_MARKERS = [
    r"objective",
    r"summary",
    r"professional\s+summary",
    r"career\s+summary",
    r"profile",
    r"education",
    r"academic\s+background",
    r"academic\s+qualifications",
    r"technical\s+skills",
    r"skills\s+and\s+competencies",
    r"key\s+skills",
    r"core\s+competencies",
    r"skills",
    r"work\s+experience",
    r"professional\s+experience",
    r"experience",
    r"employment\s+history",
    r"internships",
    r"projects",
    r"key\s+projects",
    r"academic\s+projects",
    r"certifications",
    r"certificates",
    r"licenses",
    r"awards",
    r"honors\s+and\s+awards",
    r"publications",
    r"leadership",
    r"extra-curricular\s+activities",
    r"extracurricular\s+activities",
    r"volunteer\s+experience",
    r"volunteer\s+work",
    r"achievements",
    r"languages",
    r"interests",
    r"hobbies",
]

SECTION_REGEX = re.compile(
    rf"^(?:[0-9IVX]+\.\s*)?({'|'.join(SECTION_MARKERS)})\b[:\s\-]*$",
    re.IGNORECASE | re.MULTILINE,
)

BULLET_CHARS = ("•", "-", "–", "—", "*", "▪", "▫", "►", "✓", "o", "·")


class ResumeExtractor:
    """Extracts raw and structured text from PDF, DOCX, and DOC resumes."""

    @classmethod
    def extract(cls, file_path: str, detected_type: str) -> Dict[str, Any]:
        """
        Extracts content into canonical representation.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Resume file not found at: {file_path}")

        detected_type = detected_type.lower()
        if detected_type == "pdf":
            return cls._extract_from_pdf(file_path)
        elif detected_type == "docx":
            return cls._extract_from_docx(file_path)
        elif detected_type == "doc":
            return cls._extract_from_doc(file_path)
        else:
            raise ValueError(f"Unsupported format for extraction: {detected_type}")

    @classmethod
    def _extract_from_pdf(cls, file_path: str) -> Dict[str, Any]:
        """
        High-fidelity extraction from PDF using PyMuPDF.

        Automatically detects two-column layouts (common in resumes) and reads
        the left column fully before the right column, preventing content from
        being interleaved when the two columns are read in visual (top-to-bottom
        across both columns) order.
        """
        raw_text_parts: List[str] = []
        bullets: List[str] = []
        metadata: Dict[str, Any] = {"source_type": "pdf"}

        try:
            doc = fitz.open(file_path)
            metadata["page_count"] = len(doc)
            metadata["pdf_meta"] = doc.metadata or {}

            for page_idx in range(len(doc)):
                page = doc[page_idx]
                page_width = page.rect.width

                # Get all text blocks with coordinates
                blocks = page.get_text("blocks", sort=True)
                text_blocks = [
                    b for b in blocks
                    if len(b) > 4 and isinstance(b[4], str) and b[4].strip()
                ]

                if not text_blocks:
                    continue

                # ── Multi-column detection ──────────────────────────────────
                # Check if blocks are clustered in both halves of the page.
                page_mid = page_width / 2.0
                x_mids = [(b[0] + b[2]) / 2.0 for b in text_blocks]
                left_count  = sum(1 for x in x_mids if x < page_mid)
                right_count = sum(1 for x in x_mids if x >= page_mid)

                is_two_col = (
                    left_count >= 2
                    and right_count >= 2
                    and min(left_count, right_count) / max(left_count, right_count) > 0.15
                )

                if is_two_col:
                    # Read left column top-to-bottom, then right column top-to-bottom.
                    left_blocks  = sorted(
                        [b for b in text_blocks if (b[0] + b[2]) / 2.0 < page_mid],
                        key=lambda b: b[1],
                    )
                    right_blocks = sorted(
                        [b for b in text_blocks if (b[0] + b[2]) / 2.0 >= page_mid],
                        key=lambda b: b[1],
                    )
                    ordered_blocks = left_blocks + right_blocks
                else:
                    # Single column: natural top-to-bottom order
                    ordered_blocks = sorted(text_blocks, key=lambda b: b[1])

                for b in ordered_blocks:
                    block_text = b[4].strip()
                    if not block_text:
                        continue
                    raw_text_parts.append(block_text)

                    # Collect bullet lines
                    for line in block_text.splitlines():
                        s_line = line.strip()
                        if s_line.startswith(BULLET_CHARS) or re.match(r"^\d+[\.)] +", s_line):
                            cleaned = re.sub(r"^[\s•\-–—\*▪▫►✓o·\d\.)]+\s*", "", s_line).strip()
                            if cleaned:
                                bullets.append(cleaned)

            doc.close()
        except Exception as exc:
            logger.error(f"PyMuPDF extraction error: {exc}")
            raw_text_parts, bullets = cls._extract_pdfplumber_fallback(file_path)

        full_raw_text = "\n\n".join(raw_text_parts).strip()
        sections = cls._partition_sections(full_raw_text)

        return {
            "raw_text": full_raw_text,
            "sections": sections,
            "metadata": metadata,
            "tables": [],
            "bullets": bullets,
        }

    @classmethod
    def _extract_pdfplumber_fallback(cls, file_path: str) -> Tuple[List[str], List[str]]:
        """Fallback extractor using pdfplumber."""
        parts: List[str] = []
        bullets: List[str] = []
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text(layout=True)
                    if text:
                        parts.append(text)
                        for line in text.splitlines():
                            s = line.strip()
                            if s.startswith(BULLET_CHARS):
                                bullets.append(s.lstrip("•-–—*▪▫►✓o· \t"))
        except Exception as e:
            logger.warning(f"pdfplumber fallback also encountered error: {e}")
        return parts, bullets

    @classmethod
    def _extract_from_docx(cls, file_path: str) -> Dict[str, Any]:
        """Extracts text, headings, tables, bullets, and hyperlinks from DOCX."""
        doc = docx.Document(file_path)
        raw_text_parts: List[str] = []
        bullets: List[str] = []
        tables_data: List[List[List[str]]] = []
        metadata: Dict[str, Any] = {
            "source_type": "docx",
            "paragraphs_count": len(doc.paragraphs),
            "tables_count": len(doc.tables),
        }

        # Extract paragraphs & bullets
        for p in doc.paragraphs:
            p_text = p.text.strip()
            if not p_text:
                continue

            raw_text_parts.append(p_text)

            # Check if paragraph has bullet style or bullet character
            is_bullet = False
            if p.style and "bullet" in p.style.name.lower():
                is_bullet = True
            elif p_text.startswith(BULLET_CHARS) or re.match(r"^\d+[\.\)]\s+", p_text):
                is_bullet = True

            if is_bullet:
                cleaned = re.sub(r"^[\s•\-–—\*▪▫►✓o·\d\.\)]+\s*", "", p_text).strip()
                if cleaned:
                    bullets.append(cleaned)

        # Extract tables
        for table in doc.tables:
            table_rows = []
            for row in table.rows:
                row_cells = [cell.text.strip() for cell in row.cells]
                if any(row_cells):
                    table_rows.append(row_cells)
                    # Also include table text in raw_text for completeness
                    line_cells = " | ".join(c for c in row_cells if c)
                    raw_text_parts.append(line_cells)
            if table_rows:
                tables_data.append(table_rows)

        full_raw_text = "\n\n".join(raw_text_parts).strip()
        sections = cls._partition_sections(full_raw_text)

        return {
            "raw_text": full_raw_text,
            "sections": sections,
            "metadata": metadata,
            "tables": tables_data,
            "bullets": bullets,
        }

    @classmethod
    def _extract_from_doc(cls, file_path: str) -> Dict[str, Any]:
        """Extracts text from binary DOC using Word COM on Windows or olefile stream parsing."""
        raw_text = ""
        # 1. Try Windows Word COM first for exact extraction
        try:
            import win32com.client  # type: ignore
            word = win32com.client.Dispatch("Word.Application")
            word.Visible = False
            word.DisplayAlerts = 0
            try:
                abs_path = os.path.normpath(os.path.abspath(file_path))
                wdoc = word.Documents.Open(FileName=abs_path, ReadOnly=True)
                raw_text = wdoc.Content.Text
                wdoc.Close(False)
            finally:
                word.Quit()
        except Exception as exc:
            logger.warning(f"Word COM extraction for DOC failed: {exc}")

        # 2. Fallback: text extraction from binary stream
        if not raw_text.strip():
            try:
                with open(file_path, "rb") as f:
                    content = f.read()
                # Simple ASCII/UTF-16 text chunks recovery
                ascii_matches = re.findall(rb"[\x20-\x7E\r\n]{4,}", content)
                raw_text = "\n".join(m.decode("latin1", errors="ignore") for m in ascii_matches)
            except Exception as e:
                logger.error(f"Binary DOC extraction failed: {e}")

        clean_text = raw_text.strip()
        bullets = [
            re.sub(r"^[\s•\-–—\*▪▫►✓o·\d\.\)]+\s*", "", line).strip()
            for line in clean_text.splitlines()
            if line.strip().startswith(BULLET_CHARS)
        ]
        sections = cls._partition_sections(clean_text)

        return {
            "raw_text": clean_text,
            "sections": sections,
            "metadata": {"source_type": "doc"},
            "tables": [],
            "bullets": bullets,
        }

    @classmethod
    def _partition_sections(cls, full_text: str) -> List[Dict[str, str]]:
        """Splits full text into logical section blocks based on detected headers."""
        if not full_text:
            return []

        lines = full_text.splitlines()
        sections: List[Dict[str, str]] = []
        current_title = "HEADER"
        current_content: List[str] = []

        for line in lines:
            trimmed = line.strip()
            if not trimmed:
                continue

            # Check if this line looks like a section header (short, matches section keyword)
            if len(trimmed) < 45 and SECTION_REGEX.match(trimmed):
                if current_content:
                    sections.append({
                        "title": current_title,
                        "content": "\n".join(current_content).strip(),
                    })
                    current_content = []
                current_title = trimmed.upper()
            else:
                current_content.append(trimmed)

        if current_content:
            sections.append({
                "title": current_title,
                "content": "\n".join(current_content).strip(),
            })

        return sections
