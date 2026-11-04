"""Lieux d'un CV : « Entreprise Ville, Pays » sans liste de villes ni de pays codée en dur."""

import pytest

from app.modules.candidate_profile.application.country_resolver import build_country_resolver
from app.modules.candidate_profile.domain.extraction.extractor import extract_profile
from app.modules.candidate_profile.domain.extraction.geography import (
    split_organization_and_place,
)
from app.modules.candidate_profile.domain.proposal import proposal_to_document
from app.modules.localization.infrastructure.cldr import BabelGeographyReference

_PAYS = {"france": "FR", "belgique": "BE", "royaume-uni": "GB"}


def pays(nom: str) -> str | None:
    return _PAYS.get(nom.strip().casefold())


class TestSeparation:
    @pytest.mark.parametrize(
        ("texte", "organisation", "ville"),
        [
            ("Deuswell Bordeaux, France", "Deuswell", "Bordeaux"),
            ("Université de bordeaux Talence, France", "Université de bordeaux", "Talence"),
            ("Paris, France", None, "Paris"),
        ],
    )
    def test_la_ville_est_le_dernier_mot_avant_un_pays_reconnu(
        self, texte: str, organisation: str | None, ville: str
    ) -> None:
        resultat = split_organization_and_place(texte, pays)

        assert resultat is not None
        assert (resultat.organization, resultat.city) == (organisation, ville)
        assert resultat.country == "France" if "France" in texte else True

    @pytest.mark.parametrize("texte", ["Acme Corp, Paris", "Acme Corp", "Deuswell Bordeaux"])
    def test_sans_pays_reconnu_rien_n_est_devine(self, texte: str) -> None:
        # « Paris » n'est pas un pays : « Acme Corp, Paris » reste « entreprise, ville ».
        assert split_organization_and_place(texte, pays) is None


_CV = """\
Jeanne Martin
jeanne@exemple.test

EXPÉRIENCES PROFESSIONNELLES
Fondateur
Depuis juil. 2024 Deuswell Bordeaux, France
Lancement d'une startup.

FORMATIONS
Master MIAGE
De 2024 à 2026 Université de bordeaux Talence, France
"""


class TestExperienceEtFormation:
    def test_l_entreprise_est_separee_de_la_ville(self) -> None:
        experience = extract_profile(_CV, country_of=pays).experiences[0]

        assert (experience.company, experience.location) == ("Deuswell", "Bordeaux, France")

    def test_l_etablissement_est_separe_de_la_ville(self) -> None:
        formation = extract_profile(_CV, country_of=pays).educations[0]

        assert formation.institution == "Université de bordeaux"

    def test_sans_referentiel_le_comportement_est_inchange(self) -> None:
        experience = extract_profile(_CV).experiences[0]

        assert experience.company == "Deuswell Bordeaux"


class TestContact:
    def test_la_ville_et_le_pays_sont_lus_dans_l_en_tete(self) -> None:
        texte = "Jeanne Martin\nTalence, France\n07 58 05 45 97\n\nCOMPÉTENCES\nPython\n"

        contact = extract_profile(texte, country_of=pays).contact

        assert (contact.city, contact.country_code) == ("Talence", "FR")

    def test_une_ville_sans_pays_reconnu_n_est_pas_devinee(self) -> None:
        texte = "Jeanne Martin\nTalence, Gironde\n\nCOMPÉTENCES\nPython\n"

        assert extract_profile(texte, country_of=pays).contact.city is None

    def test_le_code_postal_reste_la_regle_la_plus_sure(self) -> None:
        texte = "Jeanne Martin\n75011 Paris\n\nCOMPÉTENCES\nPython\n"

        assert extract_profile(texte).contact.city == "Paris"

    def test_identite_du_brouillon(self) -> None:
        texte = "Jeanne Martin\nTalence, France\n\nCOMPÉTENCES\nPython\n"

        identite = proposal_to_document(extract_profile(texte, country_of=pays)).identity

        assert (identite.city, identite.country_code) == ("Talence", "FR")


class TestTitreProfessionnel:
    _TEXTE = """\
marie@exemple.test

COMPÉTENCES
Python
￼
Marie Dupont
Recherche d'une alternance en SI
Étudiante en Master MIAGE, motivée par les projets à impact.

EXPÉRIENCES PROFESSIONNELLES
Développeuse
De mai 2025 à août 2025 Acme Pessac
"""

    def test_la_ligne_apres_le_nom_est_le_titre_et_le_reste_le_resume(self) -> None:
        profil = extract_profile(self._TEXTE)

        assert profil.contact.headline == "Recherche d'une alternance en SI"
        assert profil.summary == "Étudiante en Master MIAGE, motivée par les projets à impact."

    def test_une_ligne_seule_apres_le_nom_reste_un_resume(self) -> None:
        texte = self._TEXTE.replace(
            "Étudiante en Master MIAGE, motivée par les projets à impact.\n", ""
        )

        profil = extract_profile(texte)

        assert profil.contact.headline is None
        assert profil.summary == "Recherche d'une alternance en SI"

    def test_le_titre_passe_dans_le_brouillon(self) -> None:
        document = proposal_to_document(extract_profile(self._TEXTE))

        assert document.identity.headline == "Recherche d'une alternance en SI"


class TestResolveurDeNomsDePays:
    def test_reconnait_les_pays_en_francais_et_en_anglais_sans_accents_ni_casse(self) -> None:
        resolveur = build_country_resolver(BabelGeographyReference())

        assert resolveur("France") == "FR"
        assert resolveur("ROYAUME-UNI") == "GB"
        assert resolveur("Germany") == "DE"
        assert resolveur("états-unis") == "US"

    def test_une_ville_n_est_pas_un_pays(self) -> None:
        resolveur = build_country_resolver(BabelGeographyReference())

        assert resolveur("Bordeaux") is None
        assert resolveur("") is None
