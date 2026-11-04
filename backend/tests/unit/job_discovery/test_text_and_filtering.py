from datetime import UTC, datetime

from app.core.domain.value_objects import CountryCode, EmploymentType, RemoteType
from app.modules.job_discovery.application.collection import CollectionFilter
from app.modules.job_discovery.domain.criteria import SearchCriteria
from app.modules.job_discovery.domain.filtering import matches_criteria
from app.modules.job_discovery.domain.offers import NormalizedOffer
from app.modules.job_discovery.domain.text import content_hash, html_to_text, normalize_text


class TestTexte:
    def test_normalise_accents_casse_et_ponctuation(self) -> None:
        assert (
            normalize_text("  Développeur/Ingénieur  Données! ") == "developpeur ingenieur donnees"
        )

    def test_html_est_converti_en_texte_sans_balise_ni_script(self) -> None:
        html = "<p>Bonjour <b>vous</b></p><script>alert(1)</script><ul><li>A</li><li>B</li></ul>"

        texte = html_to_text(html)

        assert "alert" not in texte
        assert "<" not in texte
        assert texte.splitlines()[0] == "Bonjour vous"
        assert "A" in texte
        assert "B" in texte

    def test_html_echappe_est_decode_puis_nettoye(self) -> None:
        assert html_to_text("&lt;p&gt;Donn&amp;eacute;es&lt;/p&gt;") == "Données"

    def test_texte_vide_donne_chaine_vide(self) -> None:
        assert html_to_text("") == ""

    def test_empreinte_stable_et_sensible_au_contenu(self) -> None:
        assert content_hash("a", "b") == content_hash("a", "b")
        assert content_hash("a", "b") != content_hash("a", "c")
        assert len(content_hash("a")) == 64

    def test_l_empreinte_distingue_absent_et_vide(self) -> None:
        assert content_hash("a", None) != content_hash("a", "")
        assert content_hash("ab", "c") != content_hash("a", "bc")


def _offre(**champs: object) -> NormalizedOffer:
    valeurs: dict[str, object] = {
        "title": "Data Analyst Senior",
        "description": "Analyse SQL et Python",
        "application_url": "https://exemple.test/1",
        "content_hash": "a" * 64,
        "company_name": "Exemple SA",
        "location": "Paris, France",
    }
    valeurs.update(champs)
    return NormalizedOffer(**valeurs)  # type: ignore[arg-type]


class TestFiltrage:
    def test_intitule_insensible_aux_accents_et_a_la_casse(self) -> None:
        offre = _offre(title="Ingénieur Données")

        assert matches_criteria(offre, SearchCriteria(title="ingenieur donnees"))
        assert not matches_criteria(offre, SearchCriteria(title="comptable"))

    def test_un_intitule_alternatif_suffit(self) -> None:
        criteres = SearchCriteria(title="Business Analyst", alternative_titles=("Data Analyst",))

        assert matches_criteria(_offre(), criteres)

    def test_tous_les_mots_cles_et_competences_doivent_etre_presents(self) -> None:
        assert matches_criteria(_offre(), SearchCriteria(keywords=("sql", "python")))
        assert not matches_criteria(_offre(), SearchCriteria(keywords=("sql", "rust")))
        assert not matches_criteria(_offre(), SearchCriteria(title="Data", skills=("java",)))

    def test_ville_et_pays(self) -> None:
        paris = _offre(country_code=CountryCode("FR"))

        assert matches_criteria(paris, SearchCriteria(title="Data", city="paris"))
        assert not matches_criteria(paris, SearchCriteria(title="Data", city="Lyon"))
        assert matches_criteria(paris, SearchCriteria(title="Data", country_codes=("FR",)))
        assert not matches_criteria(paris, SearchCriteria(title="Data", country_codes=("DE",)))

    def test_information_absente_n_exclut_pas_l_offre(self) -> None:
        inconnue = _offre(location=None, company_name=None)
        criteres = SearchCriteria(
            title="Data",
            city="Lyon",
            company="Autre",
            country_codes=("DE",),
            remote_types=(RemoteType.REMOTE,),
            employment_types=(EmploymentType.PERMANENT,),
        )

        assert matches_criteria(inconnue, criteres)

    def test_information_connue_et_differente_exclut_l_offre(self) -> None:
        offre = _offre(remote_type=RemoteType.ON_SITE, employment_type=EmploymentType.FIXED_TERM)

        assert not matches_criteria(
            offre, SearchCriteria(title="Data", remote_types=(RemoteType.REMOTE,))
        )
        assert not matches_criteria(
            offre, SearchCriteria(title="Data", employment_types=(EmploymentType.PERMANENT,))
        )

    def test_date_de_publication(self) -> None:
        offre = _offre(published_at=datetime(2026, 1, 1, tzinfo=UTC))
        recent = datetime(2026, 6, 1, tzinfo=UTC)

        assert not matches_criteria(offre, SearchCriteria(title="Data", published_since=recent))
        assert matches_criteria(_offre(), SearchCriteria(title="Data", published_since=recent))

    def test_langue_compare_la_langue_de_base(self) -> None:
        offre = _offre(language="fr")

        assert matches_criteria(offre, SearchCriteria(title="Data", language="fr-CA"))
        assert not matches_criteria(offre, SearchCriteria(title="Data", language="en"))


def test_le_filtre_de_collecte_garde_les_intitules_vises_et_exige_les_mots_cles() -> None:
    def offre(titre: str, description: str = "") -> NormalizedOffer:
        return NormalizedOffer(
            title=titre,
            description=description,
            application_url="https://exemple.test/o",
            canonical_url="https://exemple.test/o",
            company_name="Exemple",
            content_hash="h",
        )

    garder = CollectionFilter(titles=("développeur", "software engineer"), keywords=("Python",))

    assert garder.keeps(offre("Développeur backend", "Stack Python"))
    assert garder.keeps(offre("Senior Software Engineer", "python et Go"))
    assert not garder.keeps(offre("Comptable", "Python"))  # intitulé non visé
    assert not garder.keeps(offre("Développeur", "Java uniquement"))  # mot-clé absent
    assert CollectionFilter().is_empty and not garder.is_empty
