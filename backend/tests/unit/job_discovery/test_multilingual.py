from app.modules.job_discovery.application.collection import CollectionFilter
from app.modules.job_discovery.domain.multilingual import expand_term
from app.modules.job_discovery.domain.offers import NormalizedOffer
from app.modules.job_intelligence.domain.matching.offer_requirements import extraire_annees


def test_un_terme_connu_est_etendu_dans_l_autre_langue_sans_doublon() -> None:
    termes = expand_term("Développeur")

    assert termes[0] == "Développeur"
    assert "developer" in termes and "software engineer" in termes
    assert len(termes) == len(set(termes))


def test_un_terme_inconnu_ou_vide_n_est_jamais_devine() -> None:
    assert expand_term("xylophoniste") == ("xylophoniste",)
    assert expand_term("   ") == ()


def test_l_extension_ignore_la_casse_et_les_accents() -> None:
    assert "data analyst" in expand_term("ANALYSTE DE DONNEES")


def _offre(titre: str) -> NormalizedOffer:
    return NormalizedOffer(
        title=titre,
        description="",
        application_url="https://exemple.test/o",
        canonical_url="https://exemple.test/o",
        company_name="Exemple",
        content_hash="h",
    )


def test_le_filtre_de_collecte_multilingue_garde_l_intitule_anglais() -> None:
    assert not CollectionFilter(titles=("développeur",)).keeps(_offre("Software Developer"))
    assert CollectionFilter(titles=("développeur",), multilingual=True).keeps(
        _offre("Software Developer")
    )


def test_l_experience_exigee_est_deduite_de_l_annonce_ou_inconnue() -> None:
    assert extraire_annees("Vous justifiez de 3 ans d'expérience.").years == 3  # type: ignore[union-attr]
    assert extraire_annees("Rejoignez une équipe sympathique.") is None
