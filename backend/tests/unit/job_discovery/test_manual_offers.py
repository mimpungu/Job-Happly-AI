import pytest

from app.modules.job_discovery.application.manual_offers import (
    InvalidManualOfferError,
    canonical_url,
)


def test_adresse_canonique_ignore_fragment_casse_de_l_hote_et_barre_finale() -> None:
    a = canonical_url("https://Group.BNPParibas/emploi/offre-123/#postuler")
    b = canonical_url("https://group.bnpparibas/emploi/offre-123")

    assert a == b == "https://group.bnpparibas/emploi/offre-123"


def test_la_requete_est_conservee_car_elle_identifie_souvent_l_offre() -> None:
    assert canonical_url("https://x.test/offre?id=1") != canonical_url("https://x.test/offre?id=2")


@pytest.mark.parametrize(
    "url",
    [
        "http://x.test/offre",
        "ftp://x.test/o",
        "javascript:alert(1)",
        "x.test/offre",
        "https://u:p@x.test/o",
    ],
)
def test_refuse_les_adresses_non_https_ou_avec_identifiants(url: str) -> None:
    with pytest.raises(InvalidManualOfferError):
        canonical_url(url)
