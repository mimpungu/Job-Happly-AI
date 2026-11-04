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
        # Titres réels observés chez un éditeur logiciel (job board public) et auparavant manqués.
        "AI Research Engineer - Datadog AI Research (DAIR)",
        "Staff Applied Scientist - Agentic Interfaces",
        "Director, Engineering - Digital Experience Monitoring",
        "Manager I, Engineering - Zero Trust Networking",
        "Distinguished Architect, AI",
        "Senior Technical Program Manager",
        "Senior Business Systems Analyst",
        "Research Manager - Post-Training for Agents",
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
        "Engineering Compensation Partner",
        "Senior Financial Systems Analyst",
        "Senior Sourcer",
        "Senior Staff Product Designer, Design Lab",
        "Senior Product Manager - Feature Flagging",
        "Commercial Sales Engineer (Sao Paulo)",
        "Enterprise Security Sales Specialist",
        "FP&A Analyst R&D",
    ],
)
def test_ecarte_les_metiers_non_informatiques(titre: str) -> None:
    assert not is_it_offer(titre)
