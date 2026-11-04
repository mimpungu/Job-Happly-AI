"""Tests du contrôle statique des sources LaTeX (sécurité de la compilation)."""

import pytest

from app.modules.document_generation.domain.latex_safety import (
    ForbiddenLaTeXError,
    validate_latex_source,
)


def _document(corps: str, preambule: str = "") -> str:
    return (
        "\\documentclass{article}\n"
        + preambule
        + "\\begin{document}\n"
        + corps
        + "\n\\end{document}"
    )


@pytest.mark.parametrize(
    "corps",
    [
        r"\input{/etc/passwd}",
        r"\include{secret}",
        r"\openin5=/etc/passwd",
        r"\immediate\write18{ls}",
        r"\newwrite\f",
        r"\read5 to \x",
        r"\catcode`\\=12",
        r"\csname inp\string ut\endcsname",
        r"\pdffilesize{/etc/passwd}",
        r"\lstinputlisting{x}",
        r"\verbatiminput{x}",
        r"\special{pdf: attach}",
    ],
)
def test_commandes_dangereuses_refusees(corps: str) -> None:
    with pytest.raises(ForbiddenLaTeXError):
        validate_latex_source(_document(corps))


@pytest.mark.parametrize("paquet", ["catchfile", "filecontents", "shellesc", "minted", "listings"])
def test_paquets_dangereux_refuses(paquet: str) -> None:
    with pytest.raises(ForbiddenLaTeXError):
        validate_latex_source(_document("x", preambule=f"\\usepackage{{{paquet}}}\n"))


def test_paquet_dangereux_dans_une_liste_avec_options() -> None:
    with pytest.raises(ForbiddenLaTeXError):
        validate_latex_source(_document("x", preambule="\\usepackage[a=b]{geometry, minted}\n"))


def test_commande_en_commentaire_est_ignoree() -> None:
    validate_latex_source(_document("Texte % \\input{x}\n\\% pourcentage"))


def test_commande_au_prefixe_voisin_n_est_pas_confondue() -> None:
    validate_latex_source(_document(r"\inputenc \included \reading \writer"))


def test_paquets_du_template_sont_acceptes() -> None:
    validate_latex_source(
        _document(
            "Bonjour",
            preambule=(
                "\\usepackage{cmap}\\usepackage[utf8]{inputenc}\\usepackage[T1]{fontenc}\n"
                "\\usepackage{lmodern,geometry,hyperref,enumitem,titlesec}\n"
            ),
        )
    )
