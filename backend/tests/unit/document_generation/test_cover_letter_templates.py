"""Template LaTeX de la lettre (TASK-013-12, 013-13) : sécurité, langues, compilation réelle."""

import io
from dataclasses import replace
from typing import Any

from pypdf import PdfReader

from app.modules.document_generation.domain.cover_letter_generator import (
    generate_cover_letter_content,
)
from app.modules.document_generation.domain.cover_letter_models import (
    CoverLetterContent,
    CoverLetterOptions,
)
from app.modules.document_generation.domain.cover_letter_templates import (
    render_latex_cover_letter,
)
from app.modules.document_generation.infrastructure.latex_compiler import IsolatedLaTeXCompiler
from tests.unit.document_generation.cover_letter_samples import (
    AUJOURDHUI,
    contexte_offre,
    profil_alice,
)


def _lettre(**options: Any) -> CoverLetterContent:
    return generate_cover_letter_content(
        profil_alice(), contexte_offre(), CoverLetterOptions(**options), today=AUJOURDHUI
    )


def _texte(pdf: bytes) -> tuple[str, int]:
    pages = PdfReader(io.BytesIO(pdf)).pages
    return "\n".join(p.extract_text() for p in pages), len(pages)


def test_structure_et_libelles_francais() -> None:
    tex = render_latex_cover_letter(_lettre())

    assert r"\textbf{Objet : Candidature au poste de Développeur Python Backend}" in tex
    assert "Madame, Monsieur," in tex
    assert "Alice Mercier" in tex
    assert r"\textbf{Doctolib}" in tex
    assert r"\documentclass[11pt,a4paper]{article}" in tex


def test_libelles_anglais() -> None:
    tex = render_latex_cover_letter(_lettre(language="en", recipient_name="Ms Smith"))

    assert r"\textbf{Subject: Application for the position of" in tex  # avant : « Objet : »
    assert "Objet" not in tex
    assert "Attn: Ms Smith" in tex
    assert "Dear Ms Smith," in tex  # en anglais, « Dear <nom> » ne suppose pas de genre


def test_cmap_charge_avant_fontenc() -> None:
    tex = render_latex_cover_letter(_lettre())
    assert tex.index(r"\usepackage{cmap}") < tex.index(r"\usepackage[T1]{fontenc}")


def test_courriel_avec_tiret_bas_valide_dans_le_lien_et_le_libelle() -> None:
    profil = profil_alice()
    lettre = replace(_lettre(), candidate_email="alice_m@example.com")
    tex = render_latex_cover_letter(lettre)

    assert r"\href{mailto:alice_m@example.com}{alice\_m@example.com}" in tex
    assert profil.identity.email  # le profil de départ n'est pas modifié


def test_texte_utilisateur_ne_peut_pas_injecter_de_commande() -> None:
    lettre = _lettre(
        custom_opening=r"\input{/etc/passwd} \write18{id} & 100% $x$ #1 _a_ {b}",
        recipient_name=r"M. \catcode`\~=0",
    )
    tex = render_latex_cover_letter(lettre)

    for dangereux in (r"\input{/etc", r"\write18{", r"\catcode`"):
        assert dangereux not in tex
    assert r"\&" in tex
    assert r"100\%" in tex


def test_pas_de_bloc_destinataire_vide() -> None:
    lettre = replace(_lettre(), recipient_company=None, recipient_department=None)
    lettre = replace(lettre, recipient_name=None)
    tex = render_latex_cover_letter(lettre)

    assert r"\textbf{}" not in tex
    assert r"\raggedleft" not in tex


def test_variante_compacte_resserre_la_mise_en_page() -> None:
    standard = render_latex_cover_letter(_lettre())
    compacte = render_latex_cover_letter(_lettre(), compact=True)

    assert r"\documentclass[10pt,a4paper]{article}" in compacte
    assert "top=1.5cm" in compacte
    assert standard != compacte


async def test_compilation_reelle_une_page_et_texte_extractible(
    compiler: IsolatedLaTeXCompiler,
) -> None:
    lettre = _lettre(motivation="J'apprécie votre approche, d'après l'œuvre de votre équipe.")
    pdf = await compiler.compile(render_latex_cover_letter(lettre))
    texte, pages = _texte(pdf)

    assert pages == 1
    assert "Madame, Monsieur," in texte
    assert "Objet : Candidature au poste de Développeur Python Backend" in texte
    assert "l'œuvre" in texte.replace("\u2019", "'")  # sans cmap : « l'÷uvre »
    assert "Alice Mercier" in texte
    assert "alice.mercier@example.com" in texte
    assert "Je vous prie d'agréer" in texte.replace("\u2019", "'")


async def test_compilation_reelle_lettre_anglaise(compiler: IsolatedLaTeXCompiler) -> None:
    pdf = await compiler.compile(
        render_latex_cover_letter(_lettre(language="en", country_code="GB"))
    )
    texte, pages = _texte(pdf)

    assert pages == 1
    assert "Subject: Application for the position of" in texte
    assert "Dear Sir or Madam," in texte
    assert "Yours faithfully," in texte
