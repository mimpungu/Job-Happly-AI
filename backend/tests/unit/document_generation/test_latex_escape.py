"""Tests unitaires de l'échappement LaTeX (TASK-012-01 et TASK-012-04)."""

from app.modules.document_generation.domain.latex_escape import latex_escape, latex_escape_url


def test_latex_escape_caracteres_speciaux() -> None:
    brut = "R&D / C# / 100% / $50k / item_1 / {test} / ~user / ^top / back\\slash"
    attendu = (
        r"R\&D / C\# / 100\% / \$50k / item\_1 / \{test\} / "
        r"\textasciitilde{}user / \textasciicircum{}top / back\textbackslash{}slash"
    )
    assert latex_escape(brut) == attendu


def test_latex_escape_preservation_accents_et_utf8() -> None:
    brut = "Développeur sénior, spécialisé en ingénierie logicielle & systèmes embarqués."
    echappe = latex_escape(brut)
    assert "Développeur sénior" in echappe
    assert "ingénierie" in echappe
    assert "systèmes embarqués" in echappe
    assert r"\&" in echappe


def test_latex_escape_texte_vide_ou_none() -> None:
    assert latex_escape(None) == ""
    assert latex_escape("") == ""
    assert latex_escape("   ") == ""


def test_latex_escape_url() -> None:
    url = "https://example.com/cv?page=1#contact%20me"
    safe = latex_escape_url(url)
    assert safe == r"https://example.com/cv?page=1\#contact\%20me"
    assert latex_escape_url(None) == ""

