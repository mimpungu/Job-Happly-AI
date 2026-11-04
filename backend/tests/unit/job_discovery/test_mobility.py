import pytest

from app.modules.job_discovery.domain.mobility import VisaSponsorship, extract_mobility


@pytest.mark.parametrize(
    "texte",
    [
        "Visa sponsorship is available for the right candidate.",
        "We offer relocation and visa support.",
        "We can sponsor your work visa.",
        "Sponsorisation de visa possible pour les profils internationaux.",
        "Prise en charge du visa et accompagnement à la relocalisation.",
    ],
)
def test_sponsoring_propose(texte: str) -> None:
    assert extract_mobility(texte).visa_sponsorship is VisaSponsorship.OFFERED


@pytest.mark.parametrize(
    "texte",
    [
        "We do not sponsor visas for this role.",
        "Unable to provide visa sponsorship.",
        "Candidates must apply without the need for visa sponsorship.",
        "Pas de sponsorisation de visa.",
        "Sponsorship is not available.",
        "We cannot sponsor work permits at this time.",
    ],
)
def test_sponsoring_refuse(texte: str) -> None:
    assert extract_mobility(texte).visa_sponsorship is VisaSponsorship.NOT_OFFERED


def test_une_negation_sur_la_ligne_l_emporte_sur_l_offre() -> None:
    assert (
        extract_mobility("No visa sponsorship available.").visa_sponsorship
        is VisaSponsorship.NOT_OFFERED
    )


def test_une_annonce_contradictoire_n_est_pas_tranchee() -> None:
    texte = "We offer visa sponsorship.\nUnfortunately we do not sponsor visas for this team."

    assert extract_mobility(texte).visa_sponsorship is None


def test_une_annonce_muette_reste_inconnue_et_non_refusee() -> None:
    info = extract_mobility("Développeur Python, équipe données, télétravail partiel.")

    assert info.visa_sponsorship is None
    assert info.work_authorization_required is None


@pytest.mark.parametrize(
    "texte",
    [
        "You must be legally authorized to work in the United States.",
        "Candidates must have the right to work in the UK.",
        "Vous devez être autorisé à travailler en France.",
        "Permis de travail valide requis.",
    ],
)
def test_exigence_d_autorisation_de_travail(texte: str) -> None:
    assert extract_mobility(texte).work_authorization_required is True
