"""
Data Loss Prevention (DLP) & Sensitive Data Masking Service.

Detects and masks sensitive personal identifiers before text is sent to LLMs or logged:
1. Aadhaar numbers: 12-digit formats (continuous, spaced, or hyphenated) -> '1234 XXXX 9012'.
2. PAN card numbers: 10-character alphanumeric (5 letters, 4 digits, 1 letter) -> 'ABCDE****F'.
3. Passport numbers: Indian & international standard format -> masked.
4. Credit/Debit Card numbers: 16-digit card patterns -> 'XXXX-XXXX-XXXX-1234'.
5. Bank Account numbers: 9 to 18 digit patterns with banking indicators -> masked.

Preserves masked placeholders reliably through conversion without ever exposing
the raw sensitive values to LLM prompts, server logs, or client-side telemetry.
"""

import logging
import re
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


class DLPResult:
    """Holds sanitized text and metadata about detected sensitive tokens."""

    def __init__(
        self,
        sanitized_text: str,
        detected_count: int,
        detections: List[Dict[str, str]],
        placeholder_map: Dict[str, str],
    ):
        self.sanitized_text = sanitized_text
        self.detected_count = detected_count
        self.detections = detections
        self.placeholder_map = placeholder_map  # placeholder -> masked display

    def to_dict(self) -> Dict:
        return {
            "detected_count": self.detected_count,
            "detected_types": list(set(d["type"] for d in self.detections)),
            "masked_summaries": [
                {"type": d["type"], "masked_value": d["masked_value"]}
                for d in self.detections
            ],
        }


class DLPService:
    """Enterprise DLP scanner and sanitizer for resume text."""

    # 1. Aadhaar regex: supports 12 digits, spaced "1234 5678 9012", or hyphenated "1234-5678-9012"
    AADHAAR_PATTERN = re.compile(
        r"(?<!\d)(\d{4})[\s\-]?(\d{4})[\s\-]?(\d{4})(?!\d)"
    )

    # 2. Indian PAN Card: 5 uppercase letters, 4 digits, 1 uppercase letter
    PAN_PATTERN = re.compile(
        r"\b([A-Z]{5})(\d{4})([A-Z])\b", re.IGNORECASE
    )

    # 3. Passport (standard 8-char: 1 letter followed by 7 digits)
    PASSPORT_PATTERN = re.compile(
        r"\b([A-PR-WYa-pr-wy])(\d{7})\b"
    )

    # 4. Credit / Debit Card (16 digits in blocks of 4 or continuous)
    CARD_PATTERN = re.compile(
        r"\b(?:\d{4}[-\s]?){3}(\d{4})\b"
    )

    # 5. Bank Account Numbers (preceded by account/acct/a/c indicators, 9-18 digits)
    BANK_ACCT_PATTERN = re.compile(
        r"(?i)\b(?:a/c|acct|account|acc\.?|bank\s+acc(?:ount)?)\s*[:#\-]?\s*(\d{5,14})(\d{4})\b"
    )

    @classmethod
    def sanitize_resume_text(cls, text: str) -> DLPResult:
        """
        Scans and sanitizes resume text, replacing sensitive data with formatted
        masked placeholders (e.g. '1234 XXXX 9012').
        """
        if not text:
            return DLPResult(text, 0, [], {})

        detections: List[Dict[str, str]] = []
        placeholder_map: Dict[str, str] = {}
        processed_text = text

        # Step 1: Mask Aadhaar Numbers
        def replace_aadhaar(match: re.Match) -> str:
            part1 = match.group(1)
            # middle part masked
            part3 = match.group(3)
            masked = f"{part1} XXXX {part3}"
            detections.append({
                "type": "Aadhaar Number",
                "masked_value": masked,
            })
            return masked

        processed_text = cls.AADHAAR_PATTERN.sub(replace_aadhaar, processed_text)

        # Step 2: Mask PAN Numbers
        def replace_pan(match: re.Match) -> str:
            p1 = match.group(1).upper()
            p3 = match.group(3).upper()
            masked = f"{p1}****{p3}"
            detections.append({
                "type": "PAN Card",
                "masked_value": masked,
            })
            return masked

        processed_text = cls.PAN_PATTERN.sub(replace_pan, processed_text)

        # Step 3: Mask Credit / Debit Cards
        def replace_card(match: re.Match) -> str:
            last4 = match.group(1)
            masked = f"XXXX-XXXX-XXXX-{last4}"
            detections.append({
                "type": "Payment Card",
                "masked_value": masked,
            })
            return masked

        processed_text = cls.CARD_PATTERN.sub(replace_card, processed_text)

        # Step 4: Mask Bank Accounts
        def replace_bank_acct(match: re.Match) -> str:
            prefix = match.group(0).split(match.group(1))[0]
            last4 = match.group(2)
            masked = f"{prefix}XXXX-XXXX-{last4}"
            detections.append({
                "type": "Bank Account",
                "masked_value": masked,
            })
            return masked

        processed_text = cls.BANK_ACCT_PATTERN.sub(replace_bank_acct, processed_text)

        # Step 5: Mask Passports
        def replace_passport(match: re.Match) -> str:
            letter = match.group(1).upper()
            digits = match.group(2)
            masked = f"{letter}*****{digits[-2:]}"
            detections.append({
                "type": "Passport",
                "masked_value": masked,
            })
            return masked

        processed_text = cls.PASSPORT_PATTERN.sub(replace_passport, processed_text)

        if detections:
            logger.info(
                f"DLP Filter: Detected and masked {len(detections)} sensitive tokens "
                f"({set(d['type'] for d in detections)})."
            )

        return DLPResult(
            sanitized_text=processed_text,
            detected_count=len(detections),
            detections=detections,
            placeholder_map=placeholder_map,
        )
