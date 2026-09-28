"""
GmailService — reads recruitment emails via the official Gmail API (OAuth2).

Auth flow (one-time, interactive, local machine only): a Google Cloud OAuth
"Desktop app" client secrets JSON is placed at settings.GMAIL_CLIENT_SECRETS_FILE.
The first call to `authenticate()` with no cached token opens a local browser
consent screen (`InstalledAppFlow.run_local_server`) and caches the resulting
refresh token at settings.GMAIL_TOKEN_FILE. Every call after that refreshes
silently. Neither file is ever logged or committed (see .gitignore).

Dedup: this service only reads + filters by what JDRepository already knows
about (`is_gmail_message_processed`); it does NOT itself mark messages
processed — RecruitmentPipeline does that once it knows the final outcome, so
a mid-pipeline crash correctly leaves the message eligible for retry instead
of being silently skipped forever.
"""
import base64
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional

from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.config import settings
from app.services.jd_repository import JDRepository

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]+")


def _html_to_text(html: str) -> str:
    """Minimal, dependency-free HTML->text: strips tags, collapses whitespace.
    Good enough for JD extraction (the LLM sees prose, not markup); not a
    general-purpose renderer."""
    text = re.sub(r"(?is)<(script|style).*?>.*?(</\1>)", " ", html)
    text = _TAG_RE.sub(" ", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = _WS_RE.sub(" ", text)
    lines = [ln.strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


@dataclass
class ParsedEmail:
    gmail_message_id: str
    sender: str = ""
    recipient: Optional[str] = None
    subject: str = ""
    body: str = ""
    received_at: Optional[datetime] = None
    attachment_filenames: List[str] = field(default_factory=list)
    attachment_text: str = ""  # concatenated extracted text from all attachments


class GmailService:
    def __init__(self, repository: Optional[JDRepository] = None):
        self.repository = repository or JDRepository()
        self._creds: Optional[Credentials] = None

    def authenticate(self) -> Credentials:
        if self._creds and self._creds.valid:
            return self._creds

        creds: Optional[Credentials] = None
        try:
            creds = Credentials.from_authorized_user_file(settings.GMAIL_TOKEN_FILE, SCOPES)
        except FileNotFoundError:
            creds = None
        except Exception as exc:
            logger.warning("Could not load cached Gmail token: %s", exc)
            creds = None

        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(GoogleAuthRequest())
            except Exception as exc:
                logger.warning("Gmail token refresh failed, will re-run consent flow: %s", exc)
                creds = None

        if not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(settings.GMAIL_CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
            with open(settings.GMAIL_TOKEN_FILE, "w", encoding="utf-8") as f:
                f.write(creds.to_json())

        self._creds = creds
        return creds

    def _build_service(self):
        creds = self.authenticate()
        return build("gmail", "v1", credentials=creds, cache_discovery=False)

    def _query(self) -> str:
        parts = [p for p in [settings.GMAIL_QUERY] if p]
        return " ".join(parts) if parts else "is:unread"

    async def sync_new_emails(self, max_results: int = 20) -> List[ParsedEmail]:
        """
        Lists candidate messages, filters out ones already processed (per
        JDRepository), fetches + parses the rest. Never raises on a single
        bad message — logs and skips it, continues the batch.
        """
        service = self._build_service()
        try:
            resp = service.users().messages().list(
                userId="me", q=self._query(), maxResults=max_results
            ).execute()
        except HttpError as exc:
            logger.error("Gmail list() failed: %s", exc)
            return []

        message_ids = [m["id"] for m in resp.get("messages", [])]
        parsed: List[ParsedEmail] = []
        for mid in message_ids:
            if await self.repository.is_gmail_message_processed(mid):
                continue
            try:
                parsed_email = await self._fetch_and_parse(service, mid)
                parsed.append(parsed_email)
            except Exception as exc:
                logger.error("Failed to fetch/parse Gmail message %s: %s", mid, exc)
        return parsed

    async def _fetch_and_parse(self, service, message_id: str) -> ParsedEmail:
        msg = service.users().messages().get(userId="me", id=message_id, format="full").execute()
        payload = msg.get("payload", {})
        headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}

        received_at = None
        date_header = headers.get("date")
        if date_header:
            try:
                received_at = parsedate_to_datetime(date_header)
            except Exception:
                received_at = None
        if received_at is None and msg.get("internalDate"):
            try:
                received_at = datetime.utcfromtimestamp(int(msg["internalDate"]) / 1000.0)
            except Exception:
                received_at = None

        body_text, attachment_filenames, attachment_text = self._walk_parts(
            service, message_id, payload
        )

        return ParsedEmail(
            gmail_message_id=message_id,
            sender=headers.get("from", ""),
            recipient=headers.get("to"),
            subject=headers.get("subject", ""),
            body=body_text,
            received_at=received_at,
            attachment_filenames=attachment_filenames,
            attachment_text=attachment_text,
        )

    def _walk_parts(self, service, message_id: str, payload: Dict[str, Any]) -> tuple[str, List[str], str]:
        """Walks the MIME tree collecting plain-text/HTML body and attachment text.
        Attachment binary extraction is delegated to AttachmentExtractor so PDF/
        DOCX parsing logic isn't duplicated (reuses the resume pipeline's
        battle-tested extractor)."""
        from app.services.attachment_extractor import AttachmentExtractor

        plain_text = ""
        html_text = ""
        attachment_filenames: List[str] = []
        attachment_texts: List[str] = []

        def walk(part: Dict[str, Any]) -> None:
            nonlocal plain_text, html_text
            mime_type = part.get("mimeType", "")
            filename = part.get("filename") or ""
            body = part.get("body", {})

            if filename:
                attachment_filenames.append(filename)
                attachment_id = body.get("attachmentId")
                if attachment_id:
                    try:
                        att = service.users().messages().attachments().get(
                            userId="me", messageId=message_id, id=attachment_id
                        ).execute()
                        raw_bytes = base64.urlsafe_b64decode(att["data"])
                        text = AttachmentExtractor.extract_text(filename, raw_bytes)
                        if text:
                            attachment_texts.append(text)
                    except Exception as exc:
                        logger.warning("Could not extract attachment '%s': %s", filename, exc)
            elif mime_type == "text/plain" and body.get("data"):
                plain_text += base64.urlsafe_b64decode(body["data"]).decode("utf-8", errors="replace")
            elif mime_type == "text/html" and body.get("data"):
                html_text += base64.urlsafe_b64decode(body["data"]).decode("utf-8", errors="replace")

            for sub_part in part.get("parts", []) or []:
                walk(sub_part)

        walk(payload)

        body_text = plain_text.strip() or _html_to_text(html_text)
        return body_text, attachment_filenames, "\n\n".join(attachment_texts)
