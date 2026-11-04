"""Templates LaTeX de CV, mono-colonne et sobres, optimisés pour les ATS (FEATURE 012.1).

- TASK-012-01 : template principal, trois styles réellement distincts.
- TASK-012-02 : sections standards, intitulés FR/EN selon la langue du document.
- TASK-012-03 : mono-colonne stricte (aucun tableau de mise en page, aucune minipage).
- TASK-012-04 : accents et caractères internationaux (voir `latex_escape`).
- TASK-012-05 : longueur adaptée (une page compacte ou deux pages aérées).

Aucune valeur de substitution n'est inventée : une donnée absente du profil est omise.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.modules.document_generation.domain.enums import LengthTarget, ResumeTemplateStyle
from app.modules.document_generation.domain.latex_escape import latex_escape, latex_escape_url

if TYPE_CHECKING:
    from app.modules.candidate_profile.domain.profile import ProfileDocument

_ONE_PAGE_MAX_EXPERIENCES = 3
_ONE_PAGE_MAX_SKILLS = 12


@dataclass(frozen=True)
class Headings:
    """Intitulés de rubriques reconnus par les ATS dans la langue du document."""

    summary: str
    experience: str
    skills: str
    education: str
    certifications: str
    languages: str
    present: str
    other_skills: str


_HEADINGS: dict[str, Headings] = {
    "fr": Headings(
        summary="Profil professionnel",
        experience="Expériences professionnelles",
        skills="Compétences techniques",
        education="Formation",
        certifications="Certifications",
        languages="Langues",
        present="Présent",
        other_skills="Autres",
    ),
    "en": Headings(
        summary="Professional summary",
        experience="Professional experience",
        skills="Technical skills",
        education="Education",
        certifications="Certifications",
        languages="Languages",
        present="Present",
        other_skills="Other",
    ),
}


def headings_for(language: str) -> Headings:
    """Intitulés de la langue demandée (français par défaut pour une langue non gérée)."""
    return _HEADINGS.get(language.split("-")[0].lower(), _HEADINGS["fr"])


@dataclass(frozen=True)
class _Layout:
    font_size: str
    margin: str
    item_sep: str
    section_before: str
    section_after: str
    sans_serif: bool
    section_rule: bool


_LAYOUTS: dict[tuple[ResumeTemplateStyle, bool], _Layout] = {
    (ResumeTemplateStyle.CLASSIC, True): _Layout(
        "10pt", "1.2cm", "1.5pt", "1.0ex plus 0.2ex minus 0.2ex", "0.6ex plus 0.1ex", False, True
    ),
    (ResumeTemplateStyle.CLASSIC, False): _Layout(
        "11pt", "1.8cm", "3pt", "1.5ex plus 0.5ex minus 0.2ex", "0.8ex plus 0.2ex", False, True
    ),
    (ResumeTemplateStyle.COMPACT, True): _Layout(
        "10pt", "1.1cm", "1pt", "0.7ex plus 0.1ex minus 0.1ex", "0.4ex", False, True
    ),
    (ResumeTemplateStyle.COMPACT, False): _Layout(
        "10pt", "1.4cm", "1.5pt", "1.0ex plus 0.2ex minus 0.2ex", "0.5ex plus 0.1ex", False, True
    ),
    (ResumeTemplateStyle.MODERN, True): _Layout(
        "10pt", "1.3cm", "1.5pt", "1.0ex plus 0.2ex minus 0.2ex", "0.6ex plus 0.1ex", True, False
    ),
    (ResumeTemplateStyle.MODERN, False): _Layout(
        "11pt", "1.9cm", "3pt", "1.5ex plus 0.5ex minus 0.2ex", "0.8ex plus 0.2ex", True, False
    ),
}


def fits_one_page(profile: ProfileDocument) -> bool:
    """Heuristique d'une page : peu d'expériences et de compétences."""
    return (
        len(profile.experiences) <= _ONE_PAGE_MAX_EXPERIENCES
        and len(profile.skills) <= _ONE_PAGE_MAX_SKILLS
    )


def render_latex_resume(
    profile: ProfileDocument,
    *,
    title: str | None = None,
    summary: str | None = None,
    length_target: LengthTarget = LengthTarget.AUTO,
    style: ResumeTemplateStyle = ResumeTemplateStyle.CLASSIC,
    highlight_skills: tuple[str, ...] = (),
    language: str = "fr",
) -> str:
    """Génère le document LaTeX complet (.tex) prêt à être compilé par pdfLaTeX."""
    layout = _LAYOUTS[(style, _decide_one_page(profile, length_target))]
    headings = headings_for(language)

    blocs = [
        _render_header(profile, title=title),
        _render_summary(summary or profile.summary, headings),
        _render_experiences(profile, headings, item_sep=layout.item_sep),
        _render_skills(profile, headings, highlight_skills=highlight_skills),
        _render_education(profile, headings, item_sep=layout.item_sep),
        _render_certifications(profile, headings),
        _render_languages(profile, headings),
    ]
    corps = "\n\n".join(bloc for bloc in blocs if bloc)

    police = "\\renewcommand{\\familydefault}{\\sfdefault}\n" if layout.sans_serif else ""
    regle = "[\\titlerule]" if layout.section_rule else ""

    return f"""% !TEX TS-program = pdflatex
% !TEX encoding = UTF-8 Unicode
% Document généré par Happly AI, style « {style.value} ».
\\documentclass[{layout.font_size},a4paper]{{article}}

% cmap AVANT fontenc : garantit l'extraction correcte du texte (accents, ligatures) par les ATS.
\\usepackage{{cmap}}
\\usepackage[utf8]{{inputenc}}
\\usepackage[T1]{{fontenc}}
\\usepackage{{lmodern}}
{police}\\usepackage{{geometry}}
\\geometry{{a4paper, margin={layout.margin}}}

\\usepackage{{hyperref}}
\\hypersetup{{colorlinks=true, linkcolor=black, urlcolor=black}}

\\usepackage{{enumitem}}
\\usepackage{{titlesec}}

% Mono-colonne stricte : flux de lecture linéaire pour les parseurs ATS.
\\pagestyle{{empty}}
\\raggedbottom
\\raggedright
\\setlength{{\\parindent}}{{0pt}}

\\titleformat{{\\section}}
    {{\\large\\bfseries\\uppercase}}
    {{}}
    {{0em}}
    {{}}{regle}
\\titlespacing*{{\\section}}{{0pt}}{{{layout.section_before}}}{{{layout.section_after}}}

\\begin{{document}}

{corps}

\\end{{document}}
"""


def _decide_one_page(profile: ProfileDocument, target: LengthTarget) -> bool:
    if target is LengthTarget.ONE_PAGE:
        return True
    if target is LengthTarget.TWO_PAGES:
        return False
    return fits_one_page(profile)


def _period(start: str, end: str) -> str:
    return f"{start} -- {end}" if (start or end) else ""


def _render_header(profile: ProfileDocument, *, title: str | None) -> str:
    identity = profile.identity
    nom = latex_escape(f"{identity.first_name or ''} {identity.last_name or ''}")
    titre_pro = latex_escape(title or identity.headline)

    coordonnees: list[str] = []
    lieu = ", ".join(filter(None, [identity.city, identity.country_code]))
    if lieu:
        coordonnees.append(latex_escape(lieu))
    if identity.phone:
        coordonnees.append(latex_escape(identity.phone))
    if identity.email:
        cible = latex_escape_url(identity.email)
        coordonnees.append(f"\\href{{mailto:{cible}}}{{{latex_escape(identity.email)}}}")

    lignes: list[str] = []
    if nom:
        lignes.append(f"{{\\LARGE\\bfseries {nom}}}")
    if titre_pro:
        lignes.append(f"{{\\large\\textbf{{{titre_pro}}}}}")
    if coordonnees:
        lignes.append(" $\\cdot$ ".join(coordonnees))
    if not lignes:
        return ""
    corps = " \\\\[0.4em]\n    ".join(lignes)
    return f"% En-tête\n\\begin{{center}}\n    {corps}\n\\end{{center}}\n\\vspace{{0.5ex}}"


def _render_summary(summary: str | None, headings: Headings) -> str:
    if not summary or not summary.strip():
        return ""
    return f"\\section*{{{headings.summary}}}\n{latex_escape(summary)}\n\\vspace{{0.5ex}}"


def _itemize(items: list[str], item_sep: str) -> list[str]:
    if not items:
        return []
    return [
        f"\\begin{{itemize}}[leftmargin=1.5em, itemsep={item_sep}, parsep=0pt]",
        *(f"  \\item {item}" for item in items),
        "\\end{itemize}",
    ]


def _render_experiences(profile: ProfileDocument, headings: Headings, *, item_sep: str) -> str:
    if not profile.experiences:
        return ""

    lignes: list[str] = [f"\\section*{{{headings.experience}}}"]
    for exp in profile.experiences:
        debut = exp.start.label() if exp.start else ""
        fin = headings.present if exp.is_current else (exp.end.label() if exp.end else "")

        titre = latex_escape(exp.title)
        entete = f"\\textbf{{{titre}}}" if titre else ""
        entreprise = latex_escape(exp.company)
        if entreprise:
            entete += f" -- \\textit{{{entreprise}}}" if entete else f"\\textit{{{entreprise}}}"
        lieu = latex_escape(exp.location)
        if lieu:
            entete += f" ({lieu})"

        periode = _period(debut, fin)
        lignes.append(f"{entete} \\hfill \\textit{{{periode}}} \\\\[0.2em]")

        items = [latex_escape(exp.description)] if exp.description else []
        items.extend(latex_escape(r) for r in exp.achievements)
        lignes.extend(_itemize([i for i in items if i], item_sep))
        lignes.append("\\vspace{0.4ex}")
    return "\n".join(lignes)


def _render_skills(
    profile: ProfileDocument, headings: Headings, *, highlight_skills: tuple[str, ...]
) -> str:
    if not profile.skills:
        return ""

    en_avant = {h.casefold() for h in highlight_skills}
    par_categorie: dict[str, list[str]] = {}
    for skill in profile.skills:
        nom = latex_escape(skill.name)
        rendu = f"\\textbf{{{nom}}}" if skill.name.casefold() in en_avant else nom
        par_categorie.setdefault(skill.category or headings.other_skills, []).append(rendu)

    items = [
        f"\\textbf{{{latex_escape(categorie)}}} : {', '.join(noms)}"
        for categorie, noms in par_categorie.items()
    ]
    lignes = [f"\\section*{{{headings.skills}}}", *_itemize(items, "2pt"), "\\vspace{0.4ex}"]
    return "\n".join(lignes)


def _render_education(profile: ProfileDocument, headings: Headings, *, item_sep: str) -> str:
    if not profile.educations:
        return ""

    lignes: list[str] = [f"\\section*{{{headings.education}}}"]
    for edu in profile.educations:
        debut = edu.start.label() if edu.start else ""
        fin = edu.end.label() if edu.end else ""

        diplome = latex_escape(edu.degree)
        ligne = f"\\textbf{{{diplome}}}" if diplome else ""
        domaine = latex_escape(edu.field_of_study)
        if domaine:
            ligne += f" ({domaine})"
        etablissement = latex_escape(edu.institution)
        if etablissement:
            ligne += f" -- \\textit{{{etablissement}}}" if ligne else f"\\textit{{{etablissement}}}"

        lignes.append(f"{ligne} \\hfill \\textit{{{_period(debut, fin)}}} \\\\[0.2em]")
        if edu.description:
            lignes.extend(_itemize([latex_escape(edu.description)], item_sep))
        lignes.append("\\vspace{0.3ex}")
    return "\n".join(lignes)


def _render_certifications(profile: ProfileDocument, headings: Headings) -> str:
    if not profile.certifications:
        return ""

    items: list[str] = []
    for cert in profile.certifications:
        texte = f"\\textbf{{{latex_escape(cert.name)}}}"
        if cert.issuer:
            texte += f" -- {latex_escape(cert.issuer)}"
        if cert.issued_on:
            texte += f" ({cert.issued_on.label()})"
        items.append(texte)
    lignes = [f"\\section*{{{headings.certifications}}}", *_itemize(items, "2pt")]
    lignes.append("\\vspace{0.4ex}")
    return "\n".join(lignes)


def _render_languages(profile: ProfileDocument, headings: Headings) -> str:
    if not profile.languages:
        return ""

    items: list[str] = []
    for lg in profile.languages:
        niveau = lg.level_text or (lg.proficiency.value if lg.proficiency else "")
        texte = f"\\textbf{{{latex_escape(lg.language_code.upper())}}}"
        if niveau:
            texte += f" ({latex_escape(niveau)})"
        items.append(texte)
    return f"\\section*{{{headings.languages}}}\n" + " $\\cdot$ ".join(items) + "\n\\vspace{0.4ex}"
