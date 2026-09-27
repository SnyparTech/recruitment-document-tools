"""
WhatsAppFormatter — deterministic ExtractedJD -> WhatsApp message text.

This is the ONLY place a WhatsApp message body gets assembled. It never lets
the LLM (or any other free-text source) generate the message directly — it
reads fields off an already-validated ExtractedJD and slots them into a
configurable WhatsAppMessageTemplate. No field is invented: a missing value
either falls back to a neutral default ("Not specified") or the whole line is
omitted, per-field, so recruiters can tell what Resdex/the JD didn't say.
"""
import re
from typing import Optional

from app.schemas.jd import ExtractedJD
from app.schemas.whatsapp import WhatsAppMessageTemplate

# WhatsApp text messages render as plain text — no HTML/markdown injection
# risk in the traditional sense, but we still strip characters that could
# break the visual template (stray backticks/asterisks/underscores are
# WhatsApp's own bold/italic/monospace markers and could make the message
# render unpredictably if a JD field contained them).
_FORMAT_CHARS_RE = re.compile(r"[*_~`]")


def _clean(text: Optional[str]) -> str:
    if not text:
        return ""
    return _FORMAT_CHARS_RE.sub("", text).strip()


class WhatsAppFormatter:
    def __init__(self, template: Optional[WhatsAppMessageTemplate] = None):
        self.template = template or WhatsAppMessageTemplate()

    def format(self, jd: ExtractedJD) -> str:
        t = self.template
        lines = [f"{t.header_emoji} {t.header_text}", ""]

        lines.append(f"{t.role_label}: {_clean(jd.job_title)}")
        lines.append("")

        if jd.location:
            lines.append(f"{t.location_label}: {_clean(', '.join(jd.location))}")
            lines.append("")

        if jd.experience and (jd.experience.min_years is not None or jd.experience.max_years is not None):
            lines.append(f"{t.experience_label}: {_format_experience(jd.experience)}")
            lines.append("")

        skills = jd.mandatory_skills or jd.skills
        if skills:
            shown = skills[: t.max_skills_shown]
            lines.append(f"{t.skills_label}:")
            for s in shown:
                lines.append(f"{t.bullet_char} {_clean(s)}")
            remaining = len(skills) - len(shown)
            if remaining > 0:
                lines.append(f"{t.bullet_char} +{remaining} more")
            lines.append("")

        if jd.notice_period:
            lines.append(f"{t.joining_label}:")
            lines.append(_clean(jd.notice_period))
            lines.append("")

        if jd.company:
            lines.append(f"{t.company_label}:")
            lines.append(_clean(jd.company))
            lines.append("")

        lines.append(t.footer_text)

        # Collapse accidental multiple-blank-lines and trim.
        message = "\n".join(lines)
        message = re.sub(r"\n{3,}", "\n\n", message).strip()
        return message


def _format_experience(exp) -> str:
    if exp.min_years is not None and exp.max_years is not None:
        return f"{_fmt_years(exp.min_years)}-{_fmt_years(exp.max_years)} Years"
    if exp.min_years is not None:
        return f"{_fmt_years(exp.min_years)}+ Years"
    if exp.max_years is not None:
        return f"Up to {_fmt_years(exp.max_years)} Years"
    return "Not specified"


def _fmt_years(n: float) -> str:
    return str(int(n)) if float(n).is_integer() else str(n)
