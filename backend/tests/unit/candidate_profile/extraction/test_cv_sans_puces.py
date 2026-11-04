"""CV dont les puces ne sont pas du texte (formes dessinées) : missions et titres se ressemblent.

Cas réel : le PDF d'un modèle graphique, lu sans aucun marqueur de puce. Le découpage ne doit pas
prendre la dernière mission d'un poste pour l'en-tête du suivant.
"""

from app.modules.candidate_profile.domain.extraction.dates import PartialDate
from app.modules.candidate_profile.domain.extraction.extractor import extract_profile

_CV = """\
Jeanne Martin

EXPÉRIENCES PROFESSIONNELLES

Fondateur & Développeur Fullstack - Acme (Startup en cours)
Depuis juil. 2024 Acme Bordeaux, France
Implication dans la stratégie produit, le design, et la vision business globale.
Intégration d'un système d'abonnements (B2C & B2B) via Stripe.
Stagiaire Ingénieur Logiciel
De mai 2025 à août 2025 Inetum Pessac
Participation au développement et à la maintenance d'applications logicielles dans un
environnement agile.
Implémentation de fonctionnalités, correction de bugs et réalisation de tests unitaires
Téléconseiller
De 2022 à 2023 Ipsos Observer Bordeaux, France
Réalisation d'enquêtes téléphoniques pour des études de marché
Respect des normes de confidentialité
Atteinte des objectifs de performance en nombre d'appels et de sondages complets
Developpeur Java (Projet Universitaire)
De 2021 à 2022 Université de bordeaux Talence, France
Implémentation de mécanismes de jeu : la gestion des niveaux, des scores et des collisions
"""


def test_une_mission_n_est_pas_prise_pour_l_en_tete_du_poste_suivant() -> None:
    experiences = extract_profile(_CV).experiences

    assert [e.title for e in experiences] == [
        "Fondateur & Développeur Fullstack",
        "Stagiaire Ingénieur Logiciel",
        "Téléconseiller",
        "Developpeur Java (Projet Universitaire)",
    ]


def test_l_entreprise_est_lue_sur_la_ligne_de_la_date_sans_le_mot_de() -> None:
    experiences = extract_profile(_CV).experiences

    assert experiences[1].company == "Inetum Pessac"
    assert experiences[2].company is not None
    assert experiences[2].company.startswith("Ipsos Observer")


def test_les_missions_restent_rattachees_a_leur_poste() -> None:
    experiences = extract_profile(_CV).experiences

    assert any("Stripe" in mission for mission in experiences[0].achievements)
    assert any(
        "tests unitaires" in m
        for m in (*experiences[1].achievements, experiences[1].description or "")
    )


_CV_ANNEE_SEULE = """\
EXPÉRIENCES PROFESSIONNELLES
Stagiaire Ingénieur Logiciel
De mai 2025 à août 2025 Inetum Pessac
Participation au développement et à la maintenance d'applications logicielles dans un
environnement agile.
Implémentation de fonctionnalités, correction de bugs et réalisation de tests unitaires
CI/CD
Mission Développement Web – Université de Bordeaux (MIAGE)
2025 Université de bordeaux Talence, France
Réalisation du site vitrine responsive pour la formation MIAGE
Intégration, SEO, CMS (Wordpress), UX, collab. avec l'équipe pédagogique.
"""


class TestMissionsEnListe:
    def test_les_lignes_sans_puce_deviennent_des_realisations(self) -> None:
        stage = extract_profile(_CV_ANNEE_SEULE).experiences[0]

        assert stage.achievements == (
            "Participation au développement et à la maintenance d'applications logicielles "
            "dans un environnement agile.",
            "Implémentation de fonctionnalités, correction de bugs et réalisation de tests "
            "unitaires CI/CD",
        )
        assert stage.description is None

    def test_une_seule_ligne_reste_une_description(self) -> None:
        texte = "EXPÉRIENCES\nAnalyste\nDe 2020 à 2022 Acme\nAnalyse des ventes mensuelles.\n"

        experience = extract_profile(texte).experiences[0]

        assert experience.description == "Analyse des ventes mensuelles."
        assert experience.achievements == ()

    def test_de_vraies_puces_gardent_le_comportement_habituel(self) -> None:
        texte = (
            "EXPÉRIENCES\nAnalyste\nDe 2020 à 2022 Acme\n"
            "Contexte du poste.\n- Rapports\n- Tableaux\n"
        )

        experience = extract_profile(texte).experiences[0]

        assert experience.achievements == ("Rapports", "Tableaux")
        assert experience.description == "Contexte du poste."


class TestAnneeSeule:
    def test_une_experience_datee_d_une_seule_annee_est_lue(self) -> None:
        experiences = extract_profile(_CV_ANNEE_SEULE).experiences

        assert [e.title for e in experiences] == [
            "Stagiaire Ingénieur Logiciel",
            "Mission Développement Web",
        ]
        mission = experiences[1]
        assert mission.company == "Université de Bordeaux (MIAGE)"
        assert (mission.start, mission.end, mission.is_current) == (PartialDate(2025), None, False)

    def test_un_titre_tronque_par_la_mise_en_page_n_est_pas_pris_pour_un_en_tete(self) -> None:
        stage = extract_profile(_CV_ANNEE_SEULE).experiences[0]

        assert "CI/CD" not in (stage.title or "")
        assert stage.company == "Inetum Pessac"

    def test_une_annee_dans_une_phrase_n_ouvre_pas_une_experience(self) -> None:
        texte = (
            "EXPÉRIENCES\nAnalyste\nDe 2020 à 2022 Acme\n"
            "2023 : lancement du produit auprès des clients\n"
        )

        assert len(extract_profile(texte).experiences) == 1

    def test_une_annee_seule_sans_organisation_n_ouvre_pas_une_experience(self) -> None:
        texte = "EXPÉRIENCES\nAnalyste\nDe 2020 à 2022 Acme\nRapport\n2023\n"

        assert len(extract_profile(texte).experiences) == 1
