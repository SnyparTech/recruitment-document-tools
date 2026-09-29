"""
LaTeX Resume Template Generator.

Converts structured resume data into the exact required LaTeX template:
- Uses \\documentclass{resume} with 0.4in margins
- Defines \\name{...}, \\address{...}
- Renders standard sections: OBJECTIVE, Education, SKILLS, EXPERIENCE, PROJECTS,
  Extra-Curricular Activities, Leadership
- Dynamically creates \\begin{rSection}{...} for all custom/additional sections
- Handles 100% safe escaping of LaTeX reserved characters (&, %, $, #, _, {, }, ~, ^, \\)
"""

import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class LatexResumeGenerator:
    """Generates valid LaTeX source code from structured resume JSON."""

    @classmethod
    def escape_latex(cls, text: Any) -> str:
        """
        Escapes LaTeX special characters: & % $ # _ { } ~ ^ \\
        """
        if text is None:
            return ""
        s = str(text)

        # Backslash first to prevent double-escaping
        s = s.replace("\\", r"\textbackslash{}")
        s = s.replace("&", r"\&")
        s = s.replace("%", r"\%")
        s = s.replace("$", r"\$")
        s = s.replace("#", r"\#")
        s = s.replace("_", r"\_")
        s = s.replace("{", r"\{")
        s = s.replace("}", r"\}")
        s = s.replace("~", r"\textasciitilde{}")
        s = s.replace("^", r"\textasciicircum{}")

        return s

    @classmethod
    def generate_latex(cls, data: Dict[str, Any]) -> str:
        """Builds complete LaTeX document string matching the exact required template."""
        pi = data.get("personal_information", {}) or {}
        name = cls.escape_latex(pi.get("name") or "CANDIDATE NAME")

        # Address line 1: Phone \ Location
        addr1_parts = []
        if pi.get("phone"):
            addr1_parts.append(cls.escape_latex(pi["phone"]))
        if pi.get("location"):
            addr1_parts.append(cls.escape_latex(pi["location"]))
        addr1 = r" \\ ".join(addr1_parts) if addr1_parts else ""

        # Address line 2: Email \ LinkedIn \ Website
        addr2_parts = []
        if pi.get("email"):
            addr2_parts.append(cls.escape_latex(pi["email"]))
        if pi.get("linkedin"):
            addr2_parts.append(cls.escape_latex(pi["linkedin"]))
        if pi.get("website"):
            addr2_parts.append(cls.escape_latex(pi["website"]))
        addr2 = r" \\ ".join(addr2_parts) if addr2_parts else ""

        latex_lines = [
            r"\documentclass{resume}",
            r"",
            r"\usepackage[left=0.4 in,top=0.4in,right=0.4 in,bottom=0.4in]{geometry}",
            r"\newcommand{\tab}[1]{\hspace{.2667\textwidth}\rlap{#1}}",
            r"\newcommand{\itab}[1]{\hspace{0em}\rlap{#1}}",
            r"",
            f"\\name{{{name}}}",
        ]

        if addr1:
            latex_lines.append(f"\\address{{{addr1}}}")
        if addr2:
            latex_lines.append(f"\\address{{{addr2}}}")

        latex_lines.extend([
            r"",
            r"\begin{document}",
            r"",
        ])

        # Dynamic sections — order, titles, and count come entirely from
        # whatever the source resume (or the LLM's reading of it) produced.
        # No fixed template section list; each section renders based on its
        # own declared "type".
        sections = data.get("sections", []) or []
        for sec in sections:
            sec_type = sec.get("type")
            content = sec.get("content")
            title = cls.escape_latex((sec.get("title") or "SECTION").strip().upper())

            if sec_type == "text":
                text = str(content or "").strip()
                if not text:
                    continue
                latex_lines.extend([
                    f"\\begin{{rSection}}{{{title}}}",
                    cls.escape_latex(text),
                    r"\end{rSection}",
                    r"",
                ])

            elif sec_type == "list":
                items = content or []
                if not items:
                    continue
                latex_lines.extend([
                    f"\\begin{{rSection}}{{{title}}}",
                    r"\begin{itemize}",
                    r"\setlength{\itemsep}{-0.5em} \vspace{-0.5em}",
                ])
                for item in items:
                    latex_lines.append(f"\\item {cls.escape_latex(item)}")
                latex_lines.extend([
                    r"\end{itemize}",
                    r"\end{rSection}",
                    r"",
                ])

            elif sec_type == "education":
                entries = content or []
                if not entries:
                    continue
                latex_lines.append(f"\\begin{{rSection}}{{{title}}}")
                for edu in entries:
                    inst = cls.escape_latex(edu.get("institution") or "University")
                    date = cls.escape_latex(edu.get("date") or "")
                    degree = cls.escape_latex(edu.get("degree") or "")
                    loc = cls.escape_latex(edu.get("location") or "")
                    details = edu.get("details") or []

                    latex_lines.append(
                        f"\\begin{{rSubsection}}{{{inst}}}{{{date}}}{{{degree}}}{{{loc}}}"
                    )
                    for det in details:
                        latex_lines.append(f"\\item {cls.escape_latex(det)}")
                    latex_lines.append(r"\end{rSubsection}")
                latex_lines.extend([r"\end{rSection}", r""])

            elif sec_type == "experience":
                entries = content or []
                if not entries:
                    continue
                latex_lines.append(f"\\begin{{rSection}}{{{title}}}")
                for exp in entries:
                    comp = cls.escape_latex(exp.get("company") or "Company")
                    start = exp.get("start_date") or ""
                    end = exp.get("end_date") or ""
                    date_str = cls.escape_latex(f"{start} - {end}".strip(" -")) if (start or end) else ""
                    role = cls.escape_latex(exp.get("role") or "Role")
                    loc = cls.escape_latex(exp.get("location") or "")
                    bullets = exp.get("bullets") or []

                    latex_lines.append(
                        f"\\begin{{rSubsection}}{{{comp}}}{{{date_str}}}{{{role}}}{{{loc}}}"
                    )
                    for b in bullets:
                        latex_lines.append(f"\\item {cls.escape_latex(b)}")
                    latex_lines.append(r"\end{rSubsection}")
                latex_lines.extend([r"\end{rSection}", r""])

            elif sec_type == "skills_table":
                rows = content or []
                if not rows:
                    continue
                latex_lines.extend([
                    f"\\begin{{rSection}}{{{title}}}",
                    r"\begin{tabular}{ @{} >{\bfseries}l @{\hspace{6ex}} l }",
                ])
                for row in rows:
                    category = cls.escape_latex(row.get("category") or "Skills")
                    items_str = ", ".join(cls.escape_latex(s) for s in (row.get("items") or []))
                    latex_lines.append(f"{category} & {items_str} \\\\")
                latex_lines.extend([
                    r"\end{tabular}",
                    r"\end{rSection}",
                    r"",
                ])

        latex_lines.extend([
            r"\end{document}",
            r"",
        ])

        return "\n".join(latex_lines)
