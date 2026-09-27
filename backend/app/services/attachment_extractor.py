"""
AttachmentExtractor — thin wrapper turning a Gmail attachment's raw bytes into
plain text, for JD extraction. Reuses ResumeExtractor for PDF/DOCX (no
duplicate parsing logic); handles plain text/HTML itself since those don't
need the resume-specific section/bullet parsing.
"""
import logging
import os
import re
import tempfile
from typing import Optional

from app.services.resume_extractor import ResumeExtractor

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")


class AttachmentExtractor:
    @classmethod
    def extract_text(cls, filename: str, raw_bytes: bytes) -> Optional[str]:
        ext = os.path.splitext(filename)[1].lower().lstrip(".")
        if ext not in ("pdf", "docx", "doc", "txt", "html", "htm"):
            logger.info("Skipping unsupported attachment type: %s", filename)
            return None

        if ext in ("txt",):
            return raw_bytes.decode("utf-8", errors="replace").strip()

        if ext in ("html", "htm"):
            text = raw_bytes.decode("utf-8", errors="replace")
            text = _TAG_RE.sub(" ", text)
            return re.sub(r"\s+", " ", text).strip()

        if ext in ("pdf", "docx", "doc"):
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
                    tmp.write(raw_bytes)
                    tmp_path = tmp.name
                result = ResumeExtractor.extract(tmp_path, ext)
                return (result.get("raw_text") or "").strip() or None
            except Exception as exc:
                logger.warning("AttachmentExtractor failed for %s: %s", filename, exc)
                return None
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass

        return None
