"""Template LaTeX pour lettre de motivation professionnelle (TASK-013-12).

Produit un document d'une seule page, sobre, aéré et élégant, conforme aux standards
de recrutement internationaux et français.
"""

from __future__ import annotations

from app.modules.document_generation.domain.cover_letter_models import CoverLetterContent
from app.modules.document_generation.domain.latex_escape import latex_escape


def render_latex_cover_letter(content: CoverLetterContent) -> str:
    """Génère le code source LaTeX (.tex) complet d'une lettre de motivation."""
    nom_candidat = latex_escape(content.candidate_name)
    adresse_candidat = latex_escape(content.candidate_address)
    email_candidat = latex_escape(content.candidate_email)
    phone_candidat = latex_escape(content.candidate_phone)

    entreprise = latex_escape(content.recipient_company)
    service = latex_escape(content.recipient_department)

    date_lieu = latex_escape(content.date_and_location)
    objet = latex_escape(content.subject)
    salutation = latex_escape(content.salutation)

    # Paragraphes du corps de texte
    p1_intro = latex_escape(content.introduction)
    p2_parcours = latex_escape(content.background_highlight)
    p3_valeur = latex_escape(content.added_value)
    p4_closing = latex_escape(content.closing_and_call_to_action)

    politesse = latex_escape(content.complimentary_close)
    signature = latex_escape(content.signature)

    # Bloc coordonnées candidat
    coord_candidat_lignes = [f"\\textbf{{{nom_candidat}}}"]
    if adresse_candidat:
        coord_candidat_lignes.append(adresse_candidat)
    if email_candidat:
        coord_candidat_lignes.append(f"\\href{{mailto:{email_candidat}}}{{{email_candidat}}}")
    if phone_candidat:
        coord_candidat_lignes.append(phone_candidat)
    bloc_expediteur = " \\\\\n".join(coord_candidat_lignes)

    # Bloc destinataire
    coord_dest_lignes = [f"\\textbf{{{entreprise}}}"]
    if service:
        coord_dest_lignes.append(service)
    bloc_destinataire = " \\\\\n".join(coord_dest_lignes)

    return f"""% !TEX TS-program = pdflatex
% !TEX encoding = UTF-8 Unicode
\\documentclass[11pt,a4paper]{{article}}

\\usepackage[utf8]{{inputenc}}
\\usepackage[T1]{{fontenc}}
\\usepackage{{lmodern}}
\\usepackage{{geometry}}
\\geometry{{a4paper, margin=2.2cm, top=2.0cm, bottom=2.0cm}}

\\usepackage{{hyperref}}
\\hypersetup{{
    colorlinks=true,
    linkcolor=black,
    urlcolor=black
}}

\\pagestyle{{empty}}
\\setlength{{\\parindent}}{{0pt}}
\\setlength{{\\parskip}}{{1.0em}}

\\begin{{document}}

% En-tête expéditeur et destinataire
\\begin{{minipage}}[t]{{0.5\\textwidth}}
{bloc_expediteur}
\\end{{minipage}}
\\hfill
\\begin{{minipage}}[t]{{0.45\\textwidth}}
\\raggedleft
{bloc_destinataire}
\\end{{minipage}}

\\vspace{{1.5em}}

\\hfill {date_lieu}

\\vspace{{1.0em}}

\\textbf{{Objet : {objet}}}

\\vspace{{0.5em}}

{salutation}

{p1_intro}

{p2_parcours}

{p3_valeur}

{p4_closing}

\\vspace{{0.5em}}

{politesse}

\\vspace{{1.5em}}

\\textbf{{{signature}}}

\\end{{document}}
"""

