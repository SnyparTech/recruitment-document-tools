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

        # 1. OBJECTIVE
        objective = data.get("objective")
        if objective and str(objective).strip():
            obj_text = cls.escape_latex(str(objective).strip())
            latex_lines.extend([
                r"\begin{rSection}{OBJECTIVE}",
                obj_text,
                r"\end{rSection}",
                r"",
            ])

        # 2. Education
        education = data.get("education", []) or []
        if education:
            latex_lines.extend([
                r"\begin{rSection}{Education}",
            ])
            for edu in education:
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
            latex_lines.extend([
                r"\end{rSection}",
                r"",
            ])

        # 3. SKILLS
        skills = data.get("skills", {}) or {}
        has_skills = any(skills.get(k) for k in ["technical_skills", "soft_skills", "additional_skills"])
        if has_skills:
            latex_lines.extend([
                r"\begin{rSection}{SKILLS}",
                r"\begin{tabular}{ @{} >{\bfseries}l @{\hspace{6ex}} l }",
            ])
            if skills.get("technical_skills"):
                tech_str = ", ".join(cls.escape_latex(s) for s in skills["technical_skills"])
                latex_lines.append(f"Technical Skills & {tech_str} \\\\")
            if skills.get("soft_skills"):
                soft_str = ", ".join(cls.escape_latex(s) for s in skills["soft_skills"])
                latex_lines.append(f"Soft Skills & {soft_str} \\\\")
            if skills.get("additional_skills"):
                add_str = ", ".join(cls.escape_latex(s) for s in skills["additional_skills"])
                latex_lines.append(f"Tools \\& Technologies & {add_str} \\\\")
            latex_lines.extend([
                r"\end{tabular}",
                r"\end{rSection}",
                r"",
            ])

        # 4. EXPERIENCE
        experience = data.get("experience", []) or []
        if experience:
            latex_lines.extend([
                r"\begin{rSection}{EXPERIENCE}",
            ])
            for exp in experience:
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
            latex_lines.extend([
                r"\end{rSection}",
                r"",
            ])

        # 5. PROJECTS
        projects = data.get("projects", []) or []
        if projects:
            latex_lines.extend([
                r"\begin{rSection}{PROJECTS}",
            ])
            for proj in projects:
                title = cls.escape_latex(proj.get("title") or "Project")
                url = proj.get("url")
                url_str = f" ({cls.escape_latex(url)})" if url else ""
                desc = cls.escape_latex(proj.get("description") or "")

                latex_lines.append(f"\\textbf{{{title}}}{url_str}")
                if desc:
                    # Break into itemize if multi-line or paragraph
                    latex_lines.append(r"\begin{itemize}")
                    latex_lines.append(r"\setlength{\itemsep}{-0.5em} \vspace{-0.5em}")
                    for d_line in desc.splitlines():
                        clean_d = d_line.strip()
                        if clean_d:
                            latex_lines.append(f"\\item {clean_d}")
                    latex_lines.append(r"\end{itemize}")
            latex_lines.extend([
                r"\end{rSection}",
                r"",
            ])

        # 6. Extra-Curricular Activities
        extra = data.get("extra_curricular_activities", []) or []
        if extra:
            latex_lines.extend([
                r"\begin{rSection}{Extra-Curricular Activities}",
                r"\begin{itemize}",
                r"\setlength{\itemsep}{-0.5em} \vspace{-0.5em}",
            ])
            for item in extra:
                latex_lines.append(f"\\item {cls.escape_latex(item)}")
            latex_lines.extend([
                r"\end{itemize}",
                r"\end{rSection}",
                r"",
            ])

        # 7. Leadership
        leadership = data.get("leadership", []) or []
        if leadership:
            latex_lines.extend([
                r"\begin{rSection}{Leadership}",
                r"\begin{itemize}",
                r"\setlength{\itemsep}{-0.5em} \vspace{-0.5em}",
            ])
            for item in leadership:
                latex_lines.append(f"\\item {cls.escape_latex(item)}")
            latex_lines.extend([
                r"\end{itemize}",
                r"\end{rSection}",
                r"",
            ])

        # 8. Dynamic Additional Sections (e.g. Certifications, Publications, Awards, etc.)
        additional = data.get("additional_sections", []) or []
        for sec in additional:
            title = cls.escape_latex(sec.get("title", "ADDITIONAL INFORMATION").strip().upper())
            items = sec.get("items", []) or []
            if not items:
                continue

            latex_lines.extend([
                f"\\begin{{rSection}}{{{title}}}",
                r"\begin{itemize}",
                r"\setlength{\itemsep}{-0.5em} \vspace{-0.5em}",
            ])
            for itm in items:
                latex_lines.append(f"\\item {cls.escape_latex(itm)}")
            latex_lines.extend([
                r"\end{itemize}",
                f"\\end{{rSection}}",
                r"",
            ])

        latex_lines.extend([
            r"\end{document}",
            r"",
        ])

        return "\n".join(latex_lines)
