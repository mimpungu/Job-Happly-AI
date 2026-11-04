"""Template LaTeX de la lettre de motivation (TASK-013-12).

Une page, sobre et aérée. Une variante compacte sert quand la lettre déborde : on resserre la
mise en page plutôt que de couper le texte.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.document_generation.domain.cover_letter_conventions import conventions_for
from app.modules.document_generation.domain.cover_letter_models import CoverLetterContent
from app.modules.document_generation.domain.latex_escape import latex_escape, latex_escape_url


@dataclass(frozen=True)
class _Layout:
    font_size: str
    geometry: str
    parskip: str


_STANDARD = _Layout("11pt", "margin=2.2cm, top=2.0cm, bottom=2.0cm", "1.0em")
_COMPACT = _Layout("10pt", "margin=1.9cm, top=1.5cm, bottom=1.5cm", "0.7em")


def _lignes(*lignes: str) -> str:
    return " \\\\\n".join(ligne for ligne in lignes if ligne)


def render_latex_cover_letter(content: CoverLetterContent, *, compact: bool = False) -> str:
    """Code source LaTeX (.tex) complet d'une lettre de motivation."""
    mise_en_page = _COMPACT if compact else _STANDARD
    libelles = conventions_for(
        language=content.language, country_code=None, recipient_name=None
    ).labels

    courriel = ""
    if content.candidate_email:
        cible = latex_escape_url(content.candidate_email)
        courriel = f"\\href{{mailto:{cible}}}{{{latex_escape(content.candidate_email)}}}"
    expediteur = _lignes(
        f"\\textbf{{{latex_escape(content.candidate_name)}}}",
        latex_escape(content.candidate_city),
        courriel,
        latex_escape(content.candidate_phone),
    )

    entreprise = latex_escape(content.recipient_company)
    attention = latex_escape(content.recipient_name)
    destinataire = _lignes(
        f"\\textbf{{{entreprise}}}" if entreprise else "",
        latex_escape(content.recipient_department),
        f"{libelles.attention} {attention}" if attention else "",
    )
    bloc_destinataire = (
        f"""\\hfill
\\begin{{minipage}}[t]{{0.45\\textwidth}}
\\raggedleft
{destinataire}
\\end{{minipage}}"""
        if destinataire
        else ""
    )

    separateur = " :" if content.language == "fr" else ":"
    paragraphes = "\n\n".join(latex_escape(p) for p in content.body_paragraphs() if p)

    return f"""% !TEX TS-program = pdflatex
% !TEX encoding = UTF-8 Unicode
\\documentclass[{mise_en_page.font_size},a4paper]{{article}}

% cmap AVANT fontenc : extraction correcte du texte (accents, ligatures) par les lecteurs de PDF.
\\usepackage{{cmap}}
\\usepackage[utf8]{{inputenc}}
\\usepackage[T1]{{fontenc}}
\\usepackage{{lmodern}}
\\usepackage{{geometry}}
\\geometry{{a4paper, {mise_en_page.geometry}}}

\\usepackage{{hyperref}}
\\hypersetup{{colorlinks=true, linkcolor=black, urlcolor=black}}

\\pagestyle{{empty}}
\\setlength{{\\parindent}}{{0pt}}
\\setlength{{\\parskip}}{{{mise_en_page.parskip}}}

\\begin{{document}}

% Expéditeur et destinataire
\\begin{{minipage}}[t]{{0.5\\textwidth}}
{expediteur}
\\end{{minipage}}
{bloc_destinataire}

\\vspace{{1.5em}}

\\hfill {latex_escape(content.date_and_location)}

\\vspace{{1.0em}}

\\textbf{{{libelles.subject_label}{separateur} {latex_escape(content.subject)}}}

\\vspace{{0.5em}}

{latex_escape(content.salutation)}

{paragraphes}

\\vspace{{0.5em}}

{latex_escape(content.complimentary_close)}

\\vspace{{1.5em}}

\\textbf{{{latex_escape(content.signature)}}}

\\end{{document}}
"""
