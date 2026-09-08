"""
High-Fidelity DOCX & PDF Resume Generator.

Generates a real, editable Microsoft Word (.docx) document formatted to match
the visual styling of the LaTeX resume template:
- Compact 0.4-inch (28.8 pt) margins.
- Prominent 18pt bold centered name header.
- Centered contact line (Phone | Location | Email | LinkedIn | Website).
- Clean uppercase section headings with solid bottom divider lines matching LaTeX \\hrule.
- Subheadings with bold institution/company and right-aligned dates & locations.
- Tight, clean bullet points with 0.25in indent and compact line spacing.
- Companion PDF generation via Word COM on Windows.
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

COLOR_PRIMARY_TEXT = RGBColor(30, 41, 59)      # Slate-800
COLOR_SECTION_HEADING = RGBColor(15, 23, 42)   # Slate-900
COLOR_MUTED_TEXT = RGBColor(100, 116, 139)     # Slate-500
COLOR_ACCENT = RGBColor(30, 41, 59)


class DocxResumeGenerator:
    """Renders structured resume JSON into a pixel-perfect editable Word document."""

    @classmethod
    def generate_docx(cls, data: Dict[str, Any], output_path: str) -> str:
        """Creates the .docx file and writes to output_path."""
        doc = docx.Document()

        # 1. Configure page margins to compact 0.4 inches matching LaTeX template
        section = doc.sections[0]
        section.orientation = WD_ORIENT.PORTRAIT
        section.top_margin = Inches(0.4)
        section.bottom_margin = Inches(0.4)
        section.left_margin = Inches(0.4)
        section.right_margin = Inches(0.4)
        section.page_width = Inches(8.5)
        section.page_height = Inches(11.0)

        # Usable page width: 8.5 - 2*0.4 = 7.7 inches
        page_content_width_inches = 7.7
        right_margin_pos = Inches(page_content_width_inches)

        # Set Normal style font
        normal_style = doc.styles["Normal"]
        normal_font = normal_style.font
        normal_font.name = "Calibri"
        normal_font.size = Pt(10)
        normal_font.color.rgb = COLOR_PRIMARY_TEXT

        pi = data.get("personal_information", {}) or {}

        # 2. Candidate Name Header (Huge, bold, centered)
        name = (pi.get("name") or "CANDIDATE NAME").strip().upper()
        p_name = doc.add_paragraph()
        p_name.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_name.paragraph_format.space_before = Pt(0)
        p_name.paragraph_format.space_after = Pt(2)
        run_name = p_name.add_run(name)
        run_name.bold = True
        run_name.font.size = Pt(17)
        run_name.font.color.rgb = COLOR_SECTION_HEADING

        # 3. Contact Line (Centered, separated by diamonds/pipes)
        contact_tokens: List[str] = []
        if pi.get("phone"):
            contact_tokens.append(str(pi["phone"]).strip())
        if pi.get("location"):
            contact_tokens.append(str(pi["location"]).strip())
        if pi.get("email"):
            contact_tokens.append(str(pi["email"]).strip())
        if pi.get("linkedin"):
            contact_tokens.append(str(pi["linkedin"]).strip())
        if pi.get("website"):
            contact_tokens.append(str(pi["website"]).strip())

        if contact_tokens:
            p_contact = doc.add_paragraph()
            p_contact.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_contact.paragraph_format.space_before = Pt(0)
            p_contact.paragraph_format.space_after = Pt(8)
            contact_str = "   ♦   ".join(contact_tokens)
            run_contact = p_contact.add_run(contact_str)
            run_contact.font.size = Pt(9.5)
            run_contact.font.color.rgb = COLOR_MUTED_TEXT

        # 4. Objective / Summary Section
        objective = data.get("objective")
        if objective and str(objective).strip():
            cls._add_section_heading(doc, "OBJECTIVE")
            p_obj = doc.add_paragraph()
            p_obj.paragraph_format.space_before = Pt(2)
            p_obj.paragraph_format.space_after = Pt(4)
            p_obj.paragraph_format.line_spacing = 1.05
            p_obj.add_run(str(objective).strip())

        # 5. Education Section
        education = data.get("education", []) or []
        if education:
            cls._add_section_heading(doc, "EDUCATION")
            for edu in education:
                inst = edu.get("institution") or "University"
                date = edu.get("date") or ""
                degree = edu.get("degree") or ""
                loc = edu.get("location") or ""
                details = edu.get("details") or []

                # Line 1: Institution (Bold) [Right tab: Date]
                cls._add_two_column_line(
                    doc,
                    left_text=inst,
                    left_bold=True,
                    right_text=date,
                    right_bold=False,
                    tab_pos=right_margin_pos,
                    space_before=Pt(3),
                    space_after=Pt(1),
                )

                # Line 2: Degree (Italic) [Right tab: Location]
                if degree or loc:
                    cls._add_two_column_line(
                        doc,
                        left_text=degree,
                        left_italic=True,
                        right_text=loc,
                        right_italic=True,
                        tab_pos=right_margin_pos,
                        space_before=Pt(0),
                        space_after=Pt(2),
                    )

                # Bullet details
                for det in details:
                    cls._add_bullet(doc, det)

        # 6. Skills Section
        skills = data.get("skills", {}) or {}
        has_skills = any(skills.get(k) for k in ["technical_skills", "soft_skills", "additional_skills"])
        if has_skills:
            cls._add_section_heading(doc, "SKILLS")
            if skills.get("technical_skills"):
                cls._add_labeled_line(doc, "Technical Skills: ", ", ".join(skills["technical_skills"]))
            if skills.get("soft_skills"):
                cls._add_labeled_line(doc, "Soft Skills: ", ", ".join(skills["soft_skills"]))
            if skills.get("additional_skills"):
                cls._add_labeled_line(doc, "Tools & Technologies: ", ", ".join(skills["additional_skills"]))

        # 7. Experience Section
        experience = data.get("experience", []) or []
        if experience:
            cls._add_section_heading(doc, "EXPERIENCE")
            for exp in experience:
                comp = exp.get("company") or "Company"
                start = exp.get("start_date") or ""
                end = exp.get("end_date") or ""
                date_str = f"{start} - {end}".strip(" -") if (start or end) else ""
                role = exp.get("role") or "Role"
                loc = exp.get("location") or ""
                bullets = exp.get("bullets") or []

                # Line 1: Company (Bold) [Right tab: Dates]
                cls._add_two_column_line(
                    doc,
                    left_text=comp,
                    left_bold=True,
                    right_text=date_str,
                    right_bold=False,
                    tab_pos=right_margin_pos,
                    space_before=Pt(3),
                    space_after=Pt(1),
                )

                # Line 2: Role (Italic) [Right tab: Location]
                if role or loc:
                    cls._add_two_column_line(
                        doc,
                        left_text=role,
                        left_italic=True,
                        right_text=loc,
                        right_italic=True,
                        tab_pos=right_margin_pos,
                        space_before=Pt(0),
                        space_after=Pt(2),
                    )

                # Bullets
                for b in bullets:
                    cls._add_bullet(doc, b)

        # 8. Projects Section
        projects = data.get("projects", []) or []
        if projects:
            cls._add_section_heading(doc, "PROJECTS")
            for proj in projects:
                title = proj.get("title") or "Project"
                url = proj.get("url")
                desc = proj.get("description") or ""

                p_proj = doc.add_paragraph()
                p_proj.paragraph_format.space_before = Pt(3)
                p_proj.paragraph_format.space_after = Pt(1)
                run_t = p_proj.add_run(title)
                run_t.bold = True
                if url:
                    run_u = p_proj.add_run(f" ({url})")
                    run_u.font.color.rgb = COLOR_MUTED_TEXT

                if desc:
                    lines = [l.strip() for l in desc.splitlines() if l.strip()]
                    for l in lines:
                        cls._add_bullet(doc, l)

        # 9. Extra-Curricular Activities
        extra = data.get("extra_curricular_activities", []) or []
        if extra:
            cls._add_section_heading(doc, "EXTRA-CURRICULAR ACTIVITIES")
            for itm in extra:
                cls._add_bullet(doc, itm)

        # 10. Leadership
        leadership = data.get("leadership", []) or []
        if leadership:
            cls._add_section_heading(doc, "LEADERSHIP")
            for itm in leadership:
                cls._add_bullet(doc, itm)

        # 11. Additional Dynamic Sections
        additional = data.get("additional_sections", []) or []
        for sec in additional:
            title = (sec.get("title") or "ADDITIONAL DETAILS").strip().upper()
            items = sec.get("items", []) or []
            if not items:
                continue

            cls._add_section_heading(doc, title)
            for itm in items:
                cls._add_bullet(doc, itm)

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        doc.save(output_path)
        logger.info(f"DOCX Resume generated successfully at: {output_path}")
        return output_path

    @classmethod
    def _add_section_heading(cls, doc: docx.Document, title: str) -> None:
        """Adds uppercase bold heading with a clean bottom rule matching LaTeX \\hrule."""
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.keep_with_next = True

        run = p.add_run(title.upper())
        run.bold = True
        run.font.size = Pt(11)
        run.font.color.rgb = COLOR_SECTION_HEADING

        # Add horizontal bottom accent line beneath the heading (matching LaTeX \hrule)
        pPr = p._p.get_or_add_pPr()
        pBdr = parse_xml(
            f'<w:pBdr {nsdecls("w")}>\n'
            f'  <w:bottom w:val="single" w:sz="6" w:space="1" w:color="334155"/>\n'
            f'</w:pBdr>'
        )
        pPr.append(pBdr)

    @classmethod
    def _add_two_column_line(
        cls,
        doc: docx.Document,
        left_text: str,
        right_text: str,
        tab_pos: Inches,
        left_bold: bool = False,
        left_italic: bool = False,
        right_bold: bool = False,
        right_italic: bool = False,
        space_before: Pt = Pt(0),
        space_after: Pt = Pt(0),
    ) -> None:
        """Creates a line with left text and right-aligned text using a right-aligned tab stop."""
        p = doc.add_paragraph()
        p.paragraph_format.space_before = space_before
        p.paragraph_format.space_after = space_after
        p.paragraph_format.keep_with_next = True

        # Add right tab stop
        p.paragraph_format.tab_stops.add_tab_stop(tab_pos, WD_TAB_ALIGNMENT.RIGHT)

        run_l = p.add_run(left_text)
        run_l.bold = left_bold
        run_l.italic = left_italic

        if right_text:
            p.add_run("\t")
            run_r = p.add_run(right_text)
            run_r.bold = right_bold
            run_r.italic = right_italic

    @classmethod
    def _add_bullet(cls, doc: docx.Document, text: str) -> None:
        """Adds a bullet point with tight spacing and clean indentation."""
        clean_text = str(text).strip().lstrip("•-–*▪ ")
        if not clean_text:
            return

        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.2)
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after = Pt(1)
        p.paragraph_format.line_spacing = 1.05

        run_bullet = p.add_run("•  ")
        run_bullet.bold = True
        run_bullet.font.size = Pt(8.5)
        run_bullet.font.color.rgb = COLOR_ACCENT

        run_t = p.add_run(clean_text)
        run_t.font.size = Pt(9.5)

    @classmethod
    def _add_labeled_line(cls, doc: docx.Document, label: str, value: str) -> None:
        """Adds a bold category label followed by items."""
        if not value:
            return
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(1.5)
        p.paragraph_format.space_after = Pt(1.5)
        p.paragraph_format.line_spacing = 1.05

        run_lbl = p.add_run(label)
        run_lbl.bold = True
        run_lbl.font.size = Pt(9.5)

        run_val = p.add_run(value)
        run_val.font.size = Pt(9.5)

    @classmethod
    def convert_docx_to_pdf(cls, docx_path: str, pdf_path: str) -> Optional[str]:
        """Converts DOCX to high-fidelity PDF via Word COM on Windows."""
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
                abs_pdf = os.path.normpath(os.path.abspath(pdf_path))
                wdoc = word.Documents.Open(FileName=abs_docx, ReadOnly=True)
                # 17 = wdFormatPDF
                wdoc.SaveAs(FileName=abs_pdf, FileFormat=17)
                wdoc.Close(False)
                logger.info(f"Generated PDF via Word COM at: {pdf_path}")
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
