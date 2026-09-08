"""
High-Fidelity DOCX Resume Generator — LaTeX Template Faithful Replica.

Generates an editable Microsoft Word (.docx) document that visually matches
the provided LaTeX resume.cls template EXACTLY:

LaTeX Template Layout:
  \\name{...}           → 18pt bold UPPERCASE centered
  \\address{...}        → centered contact lines
  \\begin{rSection}{...} → SECTION HEADING with full-width \\hrule beneath
  \\begin{rSubsection}{company}{date}{role}{location}
    → Line 1: \\textbf{company} \\hfill date  (bold company, right-aligned date)
    → Line 2: role \\hfill \\textit{location}  (italic role, italic location)
    → bullet items \\item ...
  \\end{rSubsection}

DOCX mirrors:
  - Name: 18pt Calibri bold, UPPER, centered
  - Contact: 9.5pt centered, separated by ♦
  - Section heading: 11pt bold, underline rule border
  - Two-column lines: left + right tab stop at 7.7in
  - Bullet: 0.2in indent, • character, 9.5pt
  - 0.4in margins on all sides
"""

import logging
import os
from typing import Any, Dict, List, Optional

import docx
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Inches, Pt, RGBColor

logger = logging.getLogger(__name__)

# Colour palette matching LaTeX Slate theme
COLOR_NAME          = RGBColor(0,   0,   0)    # Pure black – name header
COLOR_SECTION_HEAD  = RGBColor(0,   0,   0)    # Section headings black
COLOR_BODY          = RGBColor(30,  30,  30)   # Near-black for body text
COLOR_MUTED         = RGBColor(80,  80,  80)   # Muted for contact / location
COLOR_BULLET        = RGBColor(0,   0,   0)    # Bullet dot

# Page layout constants (matching LaTeX 0.4in margins)
MARGIN_IN           = 0.4
PAGE_WIDTH_IN       = 8.5
CONTENT_WIDTH_IN    = PAGE_WIDTH_IN - 2 * MARGIN_IN   # 7.7 in
RIGHT_TAB           = Inches(CONTENT_WIDTH_IN)

FONT_NAME           = "Times New Roman"   # Matches LaTeX default serif font


class DocxResumeGenerator:
    """
    Renders structured resume JSON into a Word document that faithfully
    replicates the visual output of the provided LaTeX resume.cls template.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def generate_docx(cls, data: Dict[str, Any], output_path: str) -> str:
        """Creates the .docx file and writes it to *output_path*."""
        doc = docx.Document()

        # ── Page layout ────────────────────────────────────────────────
        section = doc.sections[0]
        section.orientation    = WD_ORIENT.PORTRAIT
        section.top_margin     = Inches(MARGIN_IN)
        section.bottom_margin  = Inches(MARGIN_IN)
        section.left_margin    = Inches(MARGIN_IN)
        section.right_margin   = Inches(MARGIN_IN)
        section.page_width     = Inches(PAGE_WIDTH_IN)
        section.page_height    = Inches(11.0)

        # ── Default style ──────────────────────────────────────────────
        normal = doc.styles["Normal"]
        normal.font.name  = FONT_NAME
        normal.font.size  = Pt(10)
        normal.font.color.rgb = COLOR_BODY
        normal.paragraph_format.space_before = Pt(0)
        normal.paragraph_format.space_after  = Pt(0)

        pi = data.get("personal_information", {}) or {}

        # ── 1. Name header ─────────────────────────────────────────────
        name = (pi.get("name") or "CANDIDATE NAME").strip().upper()
        p_name = doc.add_paragraph()
        p_name.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_name.paragraph_format.space_before = Pt(0)
        p_name.paragraph_format.space_after  = Pt(3)
        run_name = p_name.add_run(name)
        run_name.bold        = True
        run_name.font.name   = FONT_NAME
        run_name.font.size   = Pt(18)
        run_name.font.color.rgb = COLOR_NAME

        # ── 2. Address / contact lines ─────────────────────────────────
        # Build exactly like LaTeX \address{} lines
        addr1_parts: List[str] = []
        if pi.get("phone"):
            addr1_parts.append(str(pi["phone"]).strip())
        if pi.get("location"):
            addr1_parts.append(str(pi["location"]).strip())

        addr2_parts: List[str] = []
        if pi.get("email"):
            addr2_parts.append(str(pi["email"]).strip())
        if pi.get("linkedin"):
            addr2_parts.append(str(pi["linkedin"]).strip())
        if pi.get("website"):
            addr2_parts.append(str(pi["website"]).strip())

        for parts in [addr1_parts, addr2_parts]:
            if parts:
                cls._add_contact_line(doc, "   ♦   ".join(parts))

        # Spacer below header before first section
        cls._add_thin_spacer(doc)

        # ── 3. OBJECTIVE ───────────────────────────────────────────────
        objective = data.get("objective")
        if objective and str(objective).strip():
            cls._add_section_heading(doc, "OBJECTIVE")
            p_obj = doc.add_paragraph()
            p_obj.paragraph_format.space_before = Pt(2)
            p_obj.paragraph_format.space_after  = Pt(3)
            p_obj.paragraph_format.line_spacing_rule = None
            p_obj.paragraph_format.line_spacing = 1.08
            run_obj = p_obj.add_run(str(objective).strip())
            run_obj.font.name = FONT_NAME
            run_obj.font.size = Pt(10)

        # ── 4. EDUCATION ───────────────────────────────────────────────
        education = data.get("education", []) or []
        if education:
            cls._add_section_heading(doc, "Education")
            for edu in education:
                inst   = edu.get("institution") or "University"
                date   = edu.get("date") or ""
                degree = edu.get("degree") or ""
                loc    = edu.get("location") or ""
                details= edu.get("details") or []

                # LaTeX rSubsection: Line 1 = institution (bold) \hfill date
                cls._add_rsubsection_line1(doc, inst, date, space_before=Pt(4))
                # Line 2 = degree (italic) \hfill location (italic)
                if degree or loc:
                    cls._add_rsubsection_line2(doc, degree, loc)
                for det in details:
                    cls._add_bullet(doc, det)

        # ── 5. SKILLS ──────────────────────────────────────────────────
        skills = data.get("skills", {}) or {}
        rows: List[tuple] = []
        if skills.get("technical_skills"):
            rows.append(("Technical Skills", ", ".join(skills["technical_skills"])))
        if skills.get("soft_skills"):
            rows.append(("Soft Skills", ", ".join(skills["soft_skills"])))
        if skills.get("additional_skills"):
            rows.append(("Tools & Technologies", ", ".join(skills["additional_skills"])))

        if rows:
            cls._add_section_heading(doc, "SKILLS")
            for label, value in rows:
                cls._add_skills_row(doc, label, value)

        # ── 6. EXPERIENCE ──────────────────────────────────────────────
        experience = data.get("experience", []) or []
        if experience:
            cls._add_section_heading(doc, "EXPERIENCE")
            for exp in experience:
                role    = exp.get("role") or "Role"
                company = exp.get("company") or "Company"
                loc     = exp.get("location") or ""
                start   = exp.get("start_date") or ""
                end     = exp.get("end_date") or ""
                date_str = f"{start} - {end}".strip(" -") if (start or end) else ""
                bullets = exp.get("bullets") or []

                # LaTeX template: \textbf{Role} \hfill Date
                cls._add_rsubsection_line1(doc, role, date_str, space_before=Pt(5))
                # Company \hfill \textit{location}
                if company or loc:
                    cls._add_rsubsection_line2(doc, company, loc)
                for b in bullets:
                    cls._add_bullet(doc, b)

        # ── 7. PROJECTS ────────────────────────────────────────────────
        projects = data.get("projects", []) or []
        if projects:
            cls._add_section_heading(doc, "PROJECTS")
            for proj in projects:
                title = proj.get("title") or "Project"
                url   = proj.get("url")
                desc  = proj.get("description") or ""

                p_proj = doc.add_paragraph()
                p_proj.paragraph_format.space_before = Pt(3)
                p_proj.paragraph_format.space_after  = Pt(1)
                run_t = p_proj.add_run(title + ".")
                run_t.bold       = True
                run_t.font.name  = FONT_NAME
                run_t.font.size  = Pt(10)
                if url:
                    run_u = p_proj.add_run(f"  {url}")
                    run_u.font.size  = Pt(9.5)
                    run_u.font.name  = FONT_NAME
                    run_u.font.color.rgb = COLOR_MUTED

                if desc:
                    lines = [l.strip() for l in desc.splitlines() if l.strip()]
                    for l in lines:
                        cls._add_bullet(doc, l)

        # ── 8. EXTRA-CURRICULAR ────────────────────────────────────────
        extra = data.get("extra_curricular_activities", []) or []
        if extra:
            cls._add_section_heading(doc, "Extra-Curricular Activities")
            for itm in extra:
                cls._add_bullet(doc, itm)

        # ── 9. LEADERSHIP ──────────────────────────────────────────────
        leadership = data.get("leadership", []) or []
        if leadership:
            cls._add_section_heading(doc, "Leadership")
            for itm in leadership:
                cls._add_bullet(doc, itm)

        # ── 10. ADDITIONAL DYNAMIC SECTIONS ────────────────────────────
        additional = data.get("additional_sections", []) or []
        for sec in additional:
            title = (sec.get("title") or "ADDITIONAL INFORMATION").strip()
            items = sec.get("items", []) or []
            if not items:
                continue
            cls._add_section_heading(doc, title.upper())
            for itm in items:
                cls._add_bullet(doc, itm)

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        doc.save(output_path)
        logger.info(f"DOCX Resume generated at: {output_path}")
        return output_path

    # ------------------------------------------------------------------
    # Section heading  (matches LaTeX \begin{rSection}{...})
    # ------------------------------------------------------------------

    @classmethod
    def _add_section_heading(cls, doc: docx.Document, title: str) -> None:
        """
        Adds a bold section heading with a full-width bottom border line,
        replicating the LaTeX \\hrule beneath each \\begin{rSection} heading.
        """
        p = doc.add_paragraph()
        p.paragraph_format.space_before    = Pt(9)
        p.paragraph_format.space_after     = Pt(2)
        p.paragraph_format.keep_with_next  = True

        run = p.add_run(title.upper())
        run.bold          = True
        run.font.name     = FONT_NAME
        run.font.size     = Pt(11)
        run.font.color.rgb = COLOR_SECTION_HEAD

        # Bottom border = solid 0.75pt line (matching LaTeX \hrule)
        pPr = p._p.get_or_add_pPr()
        pBdr = parse_xml(
            f'<w:pBdr {nsdecls("w")}>\n'
            f'  <w:bottom w:val="single" w:sz="6" w:space="1" w:color="000000"/>\n'
            f'</w:pBdr>'
        )
        pPr.append(pBdr)

    # ------------------------------------------------------------------
    # rSubsection line helpers
    # ------------------------------------------------------------------

    @classmethod
    def _add_rsubsection_line1(
        cls,
        doc: docx.Document,
        left_text: str,
        right_text: str,
        space_before: Pt = Pt(3),
    ) -> None:
        """
        Line 1 of rSubsection: **left_text** (bold) \\hfill right_text
        Matches LaTeX: \\textbf{institution/role} \\hfill {date}
        """
        p = doc.add_paragraph()
        p.paragraph_format.space_before   = space_before
        p.paragraph_format.space_after    = Pt(0)
        p.paragraph_format.keep_with_next = True
        p.paragraph_format.tab_stops.add_tab_stop(RIGHT_TAB, WD_TAB_ALIGNMENT.RIGHT)

        run_l = p.add_run(left_text)
        run_l.bold          = True
        run_l.font.name     = FONT_NAME
        run_l.font.size     = Pt(10)
        run_l.font.color.rgb = COLOR_BODY

        if right_text:
            p.add_run("\t")
            run_r = p.add_run(right_text)
            run_r.font.name     = FONT_NAME
            run_r.font.size     = Pt(10)
            run_r.font.color.rgb = COLOR_BODY

    @classmethod
    def _add_rsubsection_line2(
        cls,
        doc: docx.Document,
        left_text: str,
        right_text: str,
    ) -> None:
        """
        Line 2 of rSubsection: left_text (italic) \\hfill \\textit{right_text}
        Matches LaTeX: role/degree \\hfill \\textit{location}
        """
        p = doc.add_paragraph()
        p.paragraph_format.space_before   = Pt(0)
        p.paragraph_format.space_after    = Pt(1)
        p.paragraph_format.keep_with_next = True
        p.paragraph_format.tab_stops.add_tab_stop(RIGHT_TAB, WD_TAB_ALIGNMENT.RIGHT)

        run_l = p.add_run(left_text)
        run_l.italic        = True
        run_l.font.name     = FONT_NAME
        run_l.font.size     = Pt(10)
        run_l.font.color.rgb = COLOR_BODY

        if right_text:
            p.add_run("\t")
            run_r = p.add_run(right_text)
            run_r.italic        = True
            run_r.font.name     = FONT_NAME
            run_r.font.size     = Pt(10)
            run_r.font.color.rgb = COLOR_MUTED

    # ------------------------------------------------------------------
    # Skills table row
    # ------------------------------------------------------------------

    @classmethod
    def _add_skills_row(cls, doc: docx.Document, label: str, value: str) -> None:
        """
        Adds one skills row matching LaTeX tabular:
          \\textbf{Label} & value \\\\
        Rendered as a two-column paragraph using a centre tab stop.
        """
        if not value:
            return
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after  = Pt(1)
        # Use a left-indent to align with bullets, and a tab to separate label from value
        p.paragraph_format.left_indent  = Inches(0)
        tab_pos = Inches(1.6)  # label column width ~1.6 inches
        p.paragraph_format.tab_stops.add_tab_stop(tab_pos, WD_TAB_ALIGNMENT.LEFT)

        run_lbl = p.add_run(label)
        run_lbl.bold         = True
        run_lbl.font.name    = FONT_NAME
        run_lbl.font.size    = Pt(10)
        run_lbl.font.color.rgb = COLOR_BODY

        p.add_run("\t")
        run_val = p.add_run(value)
        run_val.font.name    = FONT_NAME
        run_val.font.size    = Pt(10)
        run_val.font.color.rgb = COLOR_BODY

    # ------------------------------------------------------------------
    # Bullet point
    # ------------------------------------------------------------------

    @classmethod
    def _add_bullet(cls, doc: docx.Document, text: str) -> None:
        """
        Adds a bullet matching LaTeX \\item — indented 0.2in from body margin,
        with a '•' character run in bold followed by the bullet text at 10pt.
        """
        clean_text = str(text).strip().lstrip("•-–*▪ ")
        if not clean_text:
            return

        p = doc.add_paragraph()
        p.paragraph_format.left_indent    = Inches(0.2)
        p.paragraph_format.first_line_indent = Inches(-0.15)  # hanging indent
        p.paragraph_format.space_before   = Pt(1)
        p.paragraph_format.space_after    = Pt(1)
        p.paragraph_format.line_spacing   = 1.05

        run_bullet = p.add_run("• ")
        run_bullet.bold          = True
        run_bullet.font.size     = Pt(10)
        run_bullet.font.name     = FONT_NAME
        run_bullet.font.color.rgb = COLOR_BULLET

        run_t = p.add_run(clean_text)
        run_t.font.size  = Pt(10)
        run_t.font.name  = FONT_NAME
        run_t.font.color.rgb = COLOR_BODY

    # ------------------------------------------------------------------
    # Contact line helper
    # ------------------------------------------------------------------

    @classmethod
    def _add_contact_line(cls, doc: docx.Document, text: str) -> None:
        """Adds a centered contact information line."""
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after  = Pt(1)

        run = p.add_run(text)
        run.font.size      = Pt(9.5)
        run.font.name      = FONT_NAME
        run.font.color.rgb = COLOR_BODY

    # ------------------------------------------------------------------
    # Thin spacer
    # ------------------------------------------------------------------

    @classmethod
    def _add_thin_spacer(cls, doc: docx.Document) -> None:
        """Adds a minimal vertical spacer paragraph."""
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after  = Pt(2)

    # ------------------------------------------------------------------
    # DOCX → PDF companion via Word COM (Windows)
    # ------------------------------------------------------------------

    @classmethod
    def convert_docx_to_pdf(cls, docx_path: str, pdf_path: str) -> Optional[str]:
        """Converts DOCX to high-fidelity PDF via Microsoft Word COM on Windows."""
        try:
            try:
                import pythoncom
                pythoncom.CoInitialize()
            except Exception:
                pass

            import win32com.client  # type: ignore

            word = win32com.client.Dispatch("Word.Application")
            word.Visible = False
            word.DisplayAlerts = 0
            try:
                abs_docx = os.path.normpath(os.path.abspath(docx_path))
                abs_pdf  = os.path.normpath(os.path.abspath(pdf_path))
                wdoc = word.Documents.Open(FileName=abs_docx, ReadOnly=True)
                wdoc.SaveAs(FileName=abs_pdf, FileFormat=17)  # 17 = wdFormatPDF
                wdoc.Close(False)
                logger.info(f"Generated companion PDF at: {pdf_path}")
                return pdf_path
            finally:
                try:
                    word.Quit()
                except Exception:
                    pass
                try:
                    import pythoncom
                    pythoncom.CoUninitialize()
                except Exception:
                    pass
        except Exception as exc:
            logger.warning(f"Word COM PDF conversion unavailable: {exc}")
            return None
