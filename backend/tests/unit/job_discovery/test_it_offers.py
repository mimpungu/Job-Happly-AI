import pytest

from app.modules.job_discovery.domain.it_offers import is_it_offer


@pytest.mark.parametrize(
    "titre",
    [
        "Senior Software Engineer",
        "Développeur Java H/F",
        "DevOps Engineer",
        "Data Scientist",
        "Ingénieur Cybersécurité",
        "Chef de projet IT",
        "Backend Developer (Python)",
        "Architecte Solution",
        "Engineering Manager, Payments",
    ],
)
def test_reconnait_les_metiers_informatiques(titre: str) -> None:
    assert is_it_offer(titre)


@pytest.mark.parametrize(
    "titre",
    [
        "Chargé de clientèle",
        "Conseiller en gestion de patrimoine",
        "Sales Engineer",
        "Account Executive",
        "Technical Recruiter",
        "Infirmière",
        "Product Operations Manager",
    ],
)
def test_ecarte_les_metiers_non_informatiques(titre: str) -> None:
    assert not is_it_offer(titre)
