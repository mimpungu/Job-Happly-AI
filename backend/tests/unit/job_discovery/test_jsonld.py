from pathlib import Path

from app.core.domain.value_objects import CountryCode, EmploymentType, RemoteType
from app.modules.job_discovery.infrastructure.jsonld import extract_job_postings

PAGE = (Path(__file__).resolve().parents[2] / "fixtures" / "ats" / "careers_page.html").read_text(
    encoding="utf-8"
)
URL = "https://carrieres.exemple.test/offres"


def test_extrait_uniquement_les_offres_valides() -> None:
    offres = extract_job_postings(PAGE, page_url=URL)

    assert [o.offer.title for o in offres] == ["Data Analyst", "Développeur Télétravail"]


def test_ignore_les_blocs_invalides_et_les_autres_types() -> None:
    offres = extract_job_postings(PAGE, page_url=URL)

    assert len(offres) == 2  # Organization, JSON cassé et offre sans titre écartés


def test_normalise_champs_lieu_salaire_dates() -> None:
    offre = extract_job_postings(PAGE, page_url=URL)[0]

    assert offre.external_id == "JOB-42"
    assert offre.offer.company_name == "Exemple SA"
    assert offre.offer.location == "Paris, Île-de-France, FR"
    assert offre.offer.country_code == CountryCode("FR")
    assert offre.offer.employment_type is EmploymentType.PART_TIME
    assert str(offre.offer.salary_min) == "45000"
    assert offre.offer.salary_currency == "EUR"
    assert offre.offer.published_at is not None
    assert offre.offer.expires_at is not None
    assert offre.offer.application_url == "https://carrieres.exemple.test/offres/42"


def test_la_description_est_du_texte_sans_script() -> None:
    description = extract_job_postings(PAGE, page_url=URL)[0].offer.description

    assert "Analyse de données" in description
    assert "SQL" in description
    assert "alert" not in description
    assert "<" not in description


def test_valeurs_ambigues_ou_inexploitables_restent_inconnues() -> None:
    teletravail = extract_job_postings(PAGE, page_url=URL)[1]

    assert teletravail.offer.remote_type is RemoteType.REMOTE
    assert teletravail.offer.employment_type is None  # FULL_TIME ne dit pas CDI ou CDD
    assert teletravail.offer.salary_min is None  # salaire horaire non retenu
    assert teletravail.offer.location is None
    assert teletravail.offer.published_at is None  # pas de date inventée


def test_repli_sur_l_url_de_la_page_sans_identifiant_ni_url() -> None:
    teletravail = extract_job_postings(PAGE, page_url=URL)[1]

    assert teletravail.external_id == URL
    assert teletravail.offer.application_url == URL


def test_conserve_la_donnee_brute() -> None:
    offre = extract_job_postings(PAGE, page_url=URL)[0]

    assert offre.raw_payload["identifier"]["value"] == "JOB-42"


def test_page_sans_donnees_structurees() -> None:
    assert extract_job_postings("<html><body>Rien</body></html>", page_url=URL) == []
    assert extract_job_postings("", page_url=URL) == []


def test_une_balise_script_ordinaire_n_est_pas_interpretee() -> None:
    html = '<script>{"@type":"JobPosting","title":"Piège"}</script>'

    assert extract_job_postings(html, page_url=URL) == []
