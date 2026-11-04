"""Découpage du nom complet en prénom et nom, uniquement sur une preuve présente dans le CV."""

import pytest

from app.modules.candidate_profile.domain.extraction.models import (
    ExtractedContact,
    ExtractedProfile,
)
from app.modules.candidate_profile.domain.proposal import proposal_to_document


def _identite(nom_complet: str):  # type: ignore[no-untyped-def]
    contact = ExtractedContact(full_name=nom_complet)
    return proposal_to_document(ExtractedProfile(contact=contact)).identity


@pytest.mark.parametrize(
    ("nom", "prenom", "famille"),
    [
        ("Marie Dupont", "Marie", "Dupont"),
        # Convention française : le nom de famille est écrit en capitales.
        ("Deo MIMPUNGU GRACIA", "Deo", "MIMPUNGU GRACIA"),
        ("MARTIN Jean Pierre", "Jean Pierre", "MARTIN"),
        ("Anne-Sophie DE LA TOUR", "Anne-Sophie", "DE LA TOUR"),
    ],
)
def test_les_capitales_designent_le_nom_de_famille(nom: str, prenom: str, famille: str) -> None:
    identite = _identite(nom)

    assert (identite.first_name, identite.last_name) == (prenom, famille)


@pytest.mark.parametrize("nom", ["Jean Pierre Martin", "JEAN PIERRE MARTIN", "Jean"])
def test_sans_preuve_de_casse_le_nom_n_est_pas_devine(nom: str) -> None:
    identite = _identite(nom)

    assert (identite.first_name, identite.last_name) == (None, None)
