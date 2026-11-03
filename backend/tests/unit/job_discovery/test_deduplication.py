from datetime import UTC, datetime, timedelta

import pytest

from app.modules.job_discovery.domain.deduplication import (
    assess_duplicate,
    canonicalize_url,
    description_similarity,
)
from app.modules.job_discovery.domain.offers import NormalizedOffer

DESCRIPTION = (
    "Vous rejoignez l'équipe data pour analyser les données clients avec SQL et Python, "
    "construire des tableaux de bord et fiabiliser les indicateurs de pilotage de l'activité."
)


def _offre(**champs: object) -> NormalizedOffer:
    valeurs: dict[str, object] = {
        "title": "Data Analyst (H/F)",
        "description": DESCRIPTION,
        "application_url": "https://a.test/1",
        "content_hash": "a" * 64,
        "company_name": "Exemple SA",
        "location": "Paris, France",
    }
    valeurs.update(champs)
    return NormalizedOffer(**valeurs)  # type: ignore[arg-type]


class TestUrlCanonique:
    @pytest.mark.parametrize(
        ("brute", "attendue"),
        [
            ("https://WWW.Exemple.test/offres/42/", "https://exemple.test/offres/42"),
            ("http://exemple.test/offres/42#postuler", "https://exemple.test/offres/42"),
            ("https://exemple.test:443/o", "https://exemple.test/o"),
            ("https://exemple.test:8443/o", "https://exemple.test:8443/o"),
            (
                "https://exemple.test/o?utm_source=x&id=7&utm_campaign=y",
                "https://exemple.test/o?id=7",
            ),
            ("https://exemple.test/o?b=2&a=1&gclid=zz", "https://exemple.test/o?a=1&b=2"),
            ("https://exemple.test", "https://exemple.test/"),
        ],
    )
    def test_canonicalise(self, brute: str, attendue: str) -> None:
        assert canonicalize_url(brute) == attendue

    @pytest.mark.parametrize(
        "brute", ["", "pas une url", "ftp://x.test/a", "mailto:a@b.test", "https:///x"]
    )
    def test_url_inexploitable(self, brute: str) -> None:
        assert canonicalize_url(brute) is None

    def test_l_identifiant_dans_la_requete_est_conserve(self) -> None:
        assert canonicalize_url("https://x.test/job?id=1") != canonicalize_url(
            "https://x.test/job?id=2"
        )


class TestSimilarite:
    def test_textes_identiques(self) -> None:
        assert description_similarity(DESCRIPTION, DESCRIPTION) == 1.0

    def test_textes_sans_rapport(self) -> None:
        assert (
            description_similarity(
                DESCRIPTION, "Boulanger pâtissier : pétrir la pâte chaque matin avant l'ouverture"
            )
            == 0.0
        )

    def test_insensible_a_la_casse_aux_accents_et_a_la_ponctuation(self) -> None:
        assert description_similarity(DESCRIPTION, DESCRIPTION.upper().replace("É", "E")) == 1.0

    def test_texte_trop_court_n_est_jamais_identique(self) -> None:
        assert description_similarity("", "") == 0.0
        assert description_similarity("a b", "a b") == 0.0

    def test_modification_legere_reste_tres_proche(self) -> None:
        proche = DESCRIPTION + " Télétravail partiel possible."

        assert 0.7 < description_similarity(DESCRIPTION, proche) < 1.0


class TestDoublon:
    def test_meme_url_canonique(self) -> None:
        a = _offre(canonical_url="https://www.exemple.test/o/1?utm_source=x", company_name=None)
        b = _offre(
            canonical_url="https://exemple.test/o/1/", title="Autre titre", company_name=None
        )

        verdict = assess_duplicate(a, b)

        assert verdict.duplicate
        assert verdict.reasons == ("même URL canonique",)

    def test_meme_offre_sur_deux_sources(self) -> None:
        verdict = assess_duplicate(
            _offre(),
            _offre(title="data analyst", application_url="https://b.test/9", location="Paris"),
        )

        assert verdict.duplicate
        assert verdict.score >= 0.85

    @pytest.mark.parametrize(
        ("champs", "raison"),
        [
            ({"company_name": "Autre SA"}, "entreprises différentes"),
            ({"company_name": None}, "entreprise inconnue"),
            ({"title": "Data Scientist"}, "intitulés différents"),
            ({"location": "Lyon, France"}, "lieux différents"),
            ({"location": "Paris, Canada"}, "pays différents"),
            (
                {"description": "Poste de comptable général au sein d'un cabinet parisien établi"},
                "descriptions trop différentes",
            ),
            ({"published_at": datetime(2020, 1, 1, tzinfo=UTC)}, "publications très éloignées"),
        ],
    )
    def test_une_seule_difference_suffit_a_garder_deux_offres(
        self, champs: dict[str, object], raison: str
    ) -> None:
        a = _offre(published_at=datetime(2026, 10, 1, tzinfo=UTC))
        b = _offre(**{"published_at": datetime(2026, 10, 3, tzinfo=UTC), **champs})

        verdict = assess_duplicate(a, b)

        assert not verdict.duplicate
        assert raison in verdict.reasons

    def test_lieu_inconnu_n_empeche_pas_la_fusion(self) -> None:
        assert assess_duplicate(_offre(), _offre(location=None)).duplicate

    def test_meme_poste_dans_deux_villes_reste_deux_offres(self) -> None:
        assert not assess_duplicate(
            _offre(location="Paris"), _offre(location="Marseille")
        ).duplicate

    def test_seuil_configurable(self) -> None:
        proche = _offre(description=DESCRIPTION + " Télétravail partiel possible.")

        assert not assess_duplicate(_offre(), proche, seuil_description=0.99).duplicate
        assert assess_duplicate(_offre(), proche, seuil_description=0.5).duplicate

    def test_ecart_de_publication_configurable(self) -> None:
        a = _offre(published_at=datetime(2026, 1, 1, tzinfo=UTC))
        b = _offre(published_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=30))

        assert assess_duplicate(a, b).duplicate
        assert not assess_duplicate(a, b, ecart_publication=timedelta(days=10)).duplicate
