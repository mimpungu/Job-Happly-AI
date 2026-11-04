import pytest

from app.modules.candidate_profile.domain.text_normalization import normalize_document_text as n


def test_unifie_les_fins_de_ligne_et_reduit_les_lignes_vides() -> None:
    assert n("a\r\nb\rc\n\n\n\n\nd") == "a\nb\nc\n\nd"


def test_unicode_compose_et_ligatures_depliees() -> None:
    assert n("e\u0301te\u0301") == "été"
    assert n("ﬁnancier ﬂux") == "financier flux"


def test_espaces_speciaux_et_invisibles() -> None:
    assert n("Paris\u00a0France\u202f!") == "Paris France !"
    assert n("dévelop\u00adpement\u200b") == "développement"


def test_caracteres_de_controle_retires_mais_pas_les_retours_ligne_ni_tabulations_utiles() -> None:
    assert n("a\x00b\x07c\nd") == "abc\nd"


def test_recolle_un_mot_coupe_en_fin_de_ligne() -> None:
    assert n("dévelop-\npement web") == "développement web"


@pytest.mark.parametrize("texte", ["Full-\nStack", "2020-\n2023", "e-\nmail".upper()])
def test_ne_recolle_pas_un_tiret_legitime(texte: str) -> None:
    assert "\n" in n(texte)


@pytest.mark.parametrize("puce", ["•", "▪", "●", "◦", "–", "—", "➢", "*"])
def test_puces_ramenees_a_un_tiret(puce: str) -> None:
    assert n(f"{puce} Python\n  {puce}   SQL") == "- Python\n- SQL"


def test_ne_touche_pas_aux_symboles_au_milieu_d_une_ligne() -> None:
    assert n("Paris · France – 2020") == "Paris · France – 2020"


def test_espaces_multiples_reduits() -> None:
    assert n("  Data    Analyst  \t ") == "Data Analyst"


def test_texte_vide_ou_blanc() -> None:
    assert n("") == ""
    assert n(" \n\t\n ") == ""


def test_idempotente() -> None:
    brut = "• dévelop-\npement\u00a0web\r\n\r\n\r\n\r\nﬁn"
    assert n(n(brut)) == n(brut)


def test_les_icones_de_police_sont_retirees() -> None:
    # Glyphes de la zone d'usage privé (icônes d'e-mail, de téléphone) : aucun sens textuel.
    assert n(" marie@exemple.test\n Permis B") == "marie@exemple.test\nPermis B"


def test_la_frontiere_de_colonne_survit_a_la_normalisation() -> None:
    from app.modules.candidate_profile.domain.text_columns import COLUMN_BREAK

    assert n(f"a\n{COLUMN_BREAK}\nb") == f"a\n{COLUMN_BREAK}\nb"
