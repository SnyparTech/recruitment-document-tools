"""
Regression test for a real bug: ResumeExtractor's two-column detection
misfired on a genuinely single-column resume that happens to contain a small
2-column skills table (label | values) plus right-aligned dates. The old
threshold (>=2 blocks/side, >15% balance) treated the whole page as
two-column and reordered blocks into "all left blocks, then all right
blocks" — which moved the candidate's name/contact info to AFTER the
Experience section and separated the Summary heading from its own text by
the entire Skills+Experience content.

Fixture: tests/fixtures/single_column_resume_with_skills_table.pdf — derived
from a real resume that exhibited this bug, with all PII (name, phone,
email) blank-redacted via PyMuPDF (removed, not just visually covered — the
text layer itself no longer contains it). The redaction preserves the
original page geometry that triggers the bug — a from-scratch synthetic
rebuild was tried first and did not reproduce the block layout PyMuPDF
actually produces, so this is a faithfully-shaped, PII-free derivative
rather than a synthetic approximation.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.services.resume_extractor import ResumeExtractor

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "single_column_resume_with_skills_table.pdf")


def test_fixture_contains_no_real_candidate_pii():
    """Guards against ever re-introducing the real candidate's identity into this fixture."""
    canonical = ResumeExtractor.extract(FIXTURE_PATH, "pdf")
    raw_text = canonical["raw_text"]
    for leaked in ("JAVISETTY", "9989741128", "balakrishnajv20"):
        assert leaked not in raw_text, f"Real candidate PII ('{leaked}') leaked into the test fixture"


def test_single_column_resume_with_skills_table_is_not_misdetected_as_two_column():
    assert os.path.exists(FIXTURE_PATH), f"Fixture missing at {FIXTURE_PATH}"

    canonical = ResumeExtractor.extract(FIXTURE_PATH, "pdf")
    raw_text = canonical["raw_text"]

    summary_heading_pos = raw_text.find("SUMMARY")
    summary_text_pos = raw_text.find("Senior Security Analyst")
    skills_pos = raw_text.find("SKILLS")
    experience_pos = raw_text.find("Associate Consultant")

    assert summary_heading_pos != -1 and summary_text_pos != -1
    assert skills_pos != -1 and experience_pos != -1

    # Natural single-column reading order must be preserved: SUMMARY heading
    # immediately followed by its own text, then SKILLS, then EXPERIENCE —
    # not scrambled by an incorrect two-column reordering.
    assert summary_heading_pos < summary_text_pos < skills_pos < experience_pos

    # The Summary heading and its text must be close together (not separated by
    # the entire Skills+Experience section landing in between, as happened
    # when this page was wrongly treated as two-column).
    assert summary_text_pos - summary_heading_pos < 50


def test_fixture_actually_exercises_the_old_bug_not_a_no_op_regression_test():
    """
    Proves this fixture isn't trivially passing regardless of the fix — its
    block layout must still trip the OLD, pre-fix two-column heuristic
    (>=2 blocks/side, >15% left/right balance). If this stops being true (e.g.
    someone regenerates the fixture differently), the test above would no
    longer be testing anything real.
    """
    import fitz

    doc = fitz.open(FIXTURE_PATH)
    page = doc[0]
    page_width = page.rect.width
    blocks = page.get_text("blocks", sort=True)
    text_blocks = [b for b in blocks if len(b) > 4 and isinstance(b[4], str) and b[4].strip()]
    page_mid = page_width / 2.0
    x_mids = [(b[0] + b[2]) / 2.0 for b in text_blocks]
    left_count = sum(1 for x in x_mids if x < page_mid)
    right_count = sum(1 for x in x_mids if x >= page_mid)

    old_buggy_heuristic_would_misdetect = (
        left_count >= 2
        and right_count >= 2
        and min(left_count, right_count) / max(left_count, right_count) > 0.15
    )
    assert old_buggy_heuristic_would_misdetect, (
        "This fixture no longer triggers the old two-column bug condition — "
        "it needs to be regenerated from a layout that does, or the "
        "ordering test above isn't actually exercising the fix."
    )
