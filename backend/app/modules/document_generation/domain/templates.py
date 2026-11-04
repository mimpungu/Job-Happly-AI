"""Générateur de templates LaTeX professionnels ultra-optimisés pour les ATS.

Respecte strictement les contraintes architecturales et documentaires :
- Mise en page mono-colonne stricte (TASK-012-03).
- Sections standards ATS ordonnées (TASK-012-02).
- Gestion parfaite des accents français et caractères internationaux (TASK-012-04).
- Adaptation paramétrée de la longueur : 1 page ou multi-pages (TASK-012-05).
- Échappement LaTeX sécurisé (TASK-012-01).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.modules.document_generation.domain.enums import LengthTarget, ResumeTemplateStyle
from app.modules.document_generation.domain.latex_escape import latex_escape

if TYPE_CHECKING:
    from app.modules.candidate_profile.domain.profile import ProfileDocument


def render_latex_resume(
    profile: ProfileDocument,
    *,
    title: str | None = None,
    summary: str | None = None,
    length_target: LengthTarget = LengthTarget.AUTO,
    style: ResumeTemplateStyle = ResumeTemplateStyle.CLASSIC,
    highlight_skills: tuple[str, ...] = (),
) -> str:
    """Génère le document LaTeX complet (.tex) prêt à être compilé par pdfLaTeX."""
    is_one_page = _decide_one_page(profile, length_target)

    if is_one_page:
        font_size = "10pt"
        margin = "1.2cm"
        item_sep = "1.5pt"
        section_space_before = "1.0ex plus 0.2ex minus 0.2ex"
        section_space_after = "0.6ex plus 0.1ex"
    else:
        font_size = "11pt"
        margin = "1.8cm"
        item_sep = "3pt"
        section_space_before = "1.5ex plus 0.5ex minus 0.2ex"
        section_space_after = "0.8ex plus 0.2ex"

    header_tex = _render_header(profile, title=title)
    summary_tex = _render_summary(summary or profile.summary)
    experiences_tex = _render_experiences(profile, item_sep=item_sep)
    skills_tex = _render_skills(profile, highlight_skills=highlight_skills)
    education_tex = _render_education(profile, item_sep=item_sep)
    certifications_tex = _render_certifications(profile)
    languages_tex = _render_languages(profile)

    return f"""% !TEX TS-program = pdflatex
% !TEX encoding = UTF-8 Unicode
\\documentclass[{font_size},a4paper]{{article}}

\\usepackage[utf8]{{inputenc}}
\\usepackage[T1]{{fontenc}}
\\usepackage{{lmodern}}
\\usepackage{{geometry}}
\\geometry{{a4paper, margin={margin}}}

\\usepackage{{hyperref}}
\\hypersetup{{
    colorlinks=true,
    linkcolor=black,
    urlcolor=black,
    pdfnewwindow=true
}}

\\usepackage{{enumitem}}
\\usepackage{{titlesec}}
\\usepackage{{cmap}}

% Configuration stricte mono-colonne pour parsers ATS
\\pagestyle{{empty}}
\\raggedbottom
\\raggedright
\\setlength{{\\parindent}}{{0pt}}

% Formatage sobre des rubriques
\\titleformat{{\\section}}
    {{\\large\\bfseries\\uppercase}}
    {{}}
    {{0em}}
    {{}}[\\titlerule]

\\titlespacing*{{\\section}}
    {{0pt}}
    {{{section_space_before}}}
    {{{section_space_after}}}

\\begin{{document}}

{header_tex}

{summary_tex}

{experiences_tex}

{skills_tex}

{education_tex}

{certifications_tex}

{languages_tex}

\\end{{document}}
"""


def _decide_one_page(profile: ProfileDocument, target: LengthTarget) -> bool:
    if target == LengthTarget.ONE_PAGE:
        return True
    if target == LengthTarget.TWO_PAGES:
        return False
    return len(profile.experiences) <= 3 and len(profile.skills) <= 12


def _render_header(profile: ProfileDocument, *, title: str | None) -> str:
    identity = profile.identity
    nom = latex_escape(f"{identity.first_name or ''} {identity.last_name or ''}".strip())
    if not nom:
        nom = "Candidat"

    titre_pro = latex_escape(title or identity.headline or "Professionnel")

    coordonnees: list[str] = []
    if identity.city or identity.country_code:
        lieu = ", ".join(filter(None, [identity.city, identity.country_code]))
        coordonnees.append(latex_escape(lieu))
    if identity.phone:
        coordonnees.append(latex_escape(identity.phone))
    if identity.email:
        email_clean = latex_escape(identity.email)
        coordonnees.append(f"\\href{{mailto:{email_clean}}}{{{email_clean}}}")

    contact_line = " $\\cdot$ ".join(coordonnees) if coordonnees else ""

    return f"""% En-tête
\\begin{{center}}
    {{\\LARGE\\bfseries {nom}}} \\\\[0.4em]
    {{\\large\\textbf{{{titre_pro}}}}}
    {f"\\\\[0.4em] {contact_line}" if contact_line else ""}
\\end{{center}}
\\vspace{{0.5ex}}"""


def _render_summary(summary: str | None) -> str:
    if not summary or not summary.strip():
        return ""
    safe_summary = latex_escape(summary)
    return f"""\\section*{{Profil professionnel}}
{safe_summary}
\\vspace{{0.5ex}}"""


def _render_experiences(profile: ProfileDocument, *, item_sep: str) -> str:
    if not profile.experiences:
        return ""

    lignes: list[str] = ["\\section*{Expériences professionnelles}"]

    for exp in profile.experiences:
        titre = latex_escape(exp.title or "Poste")
        entreprise = latex_escape(exp.company or "")
        lieu = latex_escape(exp.location or "")

        debut = exp.start.label() if exp.start else ""
        if exp.is_current:
            fin = "Présent"
        elif exp.end:
            fin = exp.end.label()
        else:
            fin = ""
        periode = f"{debut} -- {fin}" if (debut or fin) else ""

        entete_gauche = f"\\textbf{{{titre}}}"
        if entreprise:
            entete_gauche += f" -- \\textit{{{entreprise}}}"
        if lieu:
            entete_gauche += f" ({lieu})"

        lignes.append(f"\\textbf{{{entete_gauche}}} \\hfill \\textit{{{periode}}} \\\\[0.2em]")

        items: list[str] = []
        if exp.description:
            items.append(latex_escape(exp.description))
        for real in exp.achievements:
            items.append(latex_escape(real))

        if items:
            lignes.append(f"\\begin{{itemize}}[leftmargin=1.5em, itemsep={item_sep}, parsep=0pt]")
            for item in items:
                lignes.append(f"  \\item {item}")
            lignes.append("\\end{itemize}")
        lignes.append("\\vspace{0.4ex}")

    return "\n".join(lignes)


def _render_skills(profile: ProfileDocument, *, highlight_skills: tuple[str, ...]) -> str:
    if not profile.skills:
        return ""

    lignes: list[str] = ["\\section*{Compétences techniques}"]

    par_categorie: dict[str, list[str]] = {}
    for skill in profile.skills:
        cat = skill.category or "Général"
        nom = skill.name
        is_highlight = any(h.casefold() == nom.casefold() for h in highlight_skills)
        nom_esc = latex_escape(nom)
        item_tex = f"\\textbf{{{nom_esc}}}" if is_highlight else nom_esc
        par_categorie.setdefault(cat, []).append(item_tex)

    lignes.append("\\begin{itemize}[leftmargin=1.5em, itemsep=2pt, parsep=0pt]")
    for cat, skills in par_categorie.items():
        cat_esc = latex_escape(cat)
        skills_str = ", ".join(skills)
        lignes.append(f"  \\item \\textbf{{{cat_esc}}} : {skills_str}")
    lignes.append("\\end{itemize}")
    lignes.append("\\vspace{0.4ex}")

    return "\n".join(lignes)


def _render_education(profile: ProfileDocument, *, item_sep: str) -> str:
    if not profile.educations:
        return ""

    lignes: list[str] = ["\\section*{Formation}"]

    for edu in profile.educations:
        diplome = latex_escape(edu.degree or "Diplôme")
        etab = latex_escape(edu.institution or "")
        domaine = latex_escape(edu.field_of_study or "")

        debut = edu.start.label() if edu.start else ""
        fin = edu.end.label() if edu.end else ""
        periode = f"{debut} -- {fin}" if (debut or fin) else ""

        ligne_edu = f"\\textbf{{{diplome}}}"
        if domaine:
            ligne_edu += f" ({domaine})"
        if etab:
            ligne_edu += f" -- \\textit{{{etab}}}"

        lignes.append(f"{ligne_edu} \\hfill \\textit{{{periode}}} \\\\[0.2em]")
        if edu.description:
            lignes.append(f"\\begin{{itemize}}[leftmargin=1.5em, itemsep={item_sep}, parsep=0pt]")
            lignes.append(f"  \\item {latex_escape(edu.description)}")
            lignes.append("\\end{itemize}")
        lignes.append("\\vspace{0.3ex}")

    return "\n".join(lignes)


def _render_certifications(profile: ProfileDocument) -> str:
    if not profile.certifications:
        return ""

    lignes: list[str] = ["\\section*{Certifications}"]
    lignes.append("\\begin{itemize}[leftmargin=1.5em, itemsep=2pt, parsep=0pt]")

    for cert in profile.certifications:
        nom = latex_escape(cert.name)
        emetteur = latex_escape(cert.issuer or "")
        date_str = cert.issued_on.label() if cert.issued_on else ""

        texte = f"\\textbf{{{nom}}}"
        if emetteur:
            texte += f" -- {emetteur}"
        if date_str:
            texte += f" ({date_str})"
        lignes.append(f"  \\item {texte}")

    lignes.append("\\end{itemize}")
    lignes.append("\\vspace{0.4ex}")
    return "\n".join(lignes)


def _render_languages(profile: ProfileDocument) -> str:
    if not profile.languages:
        return ""

    lignes: list[str] = ["\\section*{Langues}"]
    items: list[str] = []

    for lg in profile.languages:
        code = lg.language_code.upper()
        niveau = lg.level_text or (lg.proficiency.value if lg.proficiency else "")
        niveau_esc = latex_escape(niveau) if niveau else ""
        item_str = f"\\textbf{{{latex_escape(code)}}}"
        if niveau_esc:
            item_str += f" ({niveau_esc})"
        items.append(item_str)

    lignes.append(" $\\cdot$ ".join(items))
    lignes.append("\\vspace{0.4ex}")
    return "\n".join(lignes)
