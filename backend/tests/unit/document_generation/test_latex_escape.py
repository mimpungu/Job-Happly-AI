"""Tests de l'assainissement et de l'échappement LaTeX (TASK-012-01 et TASK-012-04)."""

import pytest

from app.modules.document_generation.domain.latex_escape import (
    UnsupportedCharactersError,
    latex_escape,
    latex_escape_url,
    sanitize_text,
)


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
    assert "systèmes embarqués" in echappe
    assert r"\&" in echappe


def test_latex_escape_texte_vide_ou_none() -> None:
    assert latex_escape(None) == ""
    assert latex_escape("") == ""
    assert latex_escape("   ") == ""


@pytest.mark.parametrize(
    ("brut", "attendu"),
    [
        ("A -- B", "A -{}- B"),  # sinon TeX produit un tiret demi-cadratin
        ("A --- B", "A -{}-{}- B"),
        ("<<texte>>", "<{}<texte>{}>"),  # sinon TeX produit des guillemets « »
        ("l''autre", "l'{}'autre"),
        ("a`b", r"a\textasciigrave{}b"),
    ],
)
def test_latex_escape_neutralise_les_ligatures_typographiques(brut: str, attendu: str) -> None:
    assert latex_escape(brut) == attendu


@pytest.mark.parametrize(
    ("brut", "attendu"),
    [
        ("score ≥ 5 → ok", "score >= 5 -> ok"),
        ("a\u00a0b\u202fc", "a b c"),  # espaces insécables
        ("Prix\u00adlist", "Prixlist"),  # trait d'union conditionnel
        ("fiable \U0001f680 rapide", "fiable  rapide"),  # emoji retiré
        ("a\u200bb", "ab"),  # espace de largeur nulle
        ("Łukasz Nowak, Łódź", "Łukasz Nowak, Łódź"),  # latin étendu A conservé
        ("Nguyễn Văn", "Nguyen Văn"),  # hors T1 : réduit à la base ; Latin étendu A conservé
        ("ﬁnance", "finance"),  # ligature typographique
    ],
)
def test_sanitize_text_symboles_et_caracteres_rares(brut: str, attendu: str) -> None:
    assert sanitize_text(brut) == attendu


@pytest.mark.parametrize("brut", ["Иван Петров", "日本語", "Αθήνα", "محمد"])
def test_ecritures_non_latines_levent_une_erreur_explicite(brut: str) -> None:
    """Jamais de suppression silencieuse du nom d'un candidat."""
    with pytest.raises(UnsupportedCharactersError) as erreur:
        latex_escape(brut)
    assert brut[0] in erreur.value.characters


def test_latex_escape_url() -> None:
    url = "https://example.com/cv?page=1#contact%20me"
    assert latex_escape_url(url) == r"https://example.com/cv?page=1\#contact\%20me"
    assert latex_escape_url(None) == ""


def test_latex_escape_url_retire_accolades_espaces_et_antislash() -> None:
    assert latex_escape_url("mailto:a b{c}\\d@x.fr") == "mailto:abcd@x.fr"
