import pytest

from app.modules.job_intelligence.domain.matching.offer_requirements import (
    Importance,
    extract_requirements,
    extraire_annees,
    extraire_formation,
    niveau_d_etudes,
)

from .offers import OFFRE_EN, OFFRE_FR, OFFRE_SANS_STRUCTURE


class TestAnnees:
    @pytest.mark.parametrize(
        ("texte", "annees", "obligatoire"),
        [
            ("Minimum 3 ans d'expérience en analyse", 3, True),
            ("3 ans d'expérience souhaités", 3, False),
            ("5+ years of experience in data engineering", 5, False),
            ("Expérience de 2 à 4 ans sur un poste similaire", 2, False),
            ("3 à 5 ans d'expérience", 3, False),
            ("At least 4 years experience required", 4, True),
            ("expérience : 7 ans", 7, False),
            ("1 an d'expérience", 1, False),
            ("Débutant accepté", 0, False),
            ("No experience required", 0, False),
        ],
    )
    def test_formats_courants(self, texte: str, annees: int, obligatoire: bool) -> None:
        req = extraire_annees(texte)

        assert req is not None
        assert (req.years, req.mandatory) == (annees, obligatoire)

    @pytest.mark.parametrize(
        "texte",
        [
            "Entreprise fondée il y a 10 ans",
            "Un poste de 3 jours par semaine",
            "Notre expérience client est reconnue",
            "Salaire 45 000 euros",
            "",
        ],
    )
    def test_ne_confond_pas_avec_d_autres_nombres(self, texte: str) -> None:
        assert extraire_annees(texte) is None

    def test_garde_le_plus_petit_minimum(self) -> None:
        req = extraire_annees("5 ans d'expérience en entreprise\nou 2 ans d'expérience en conseil")

        assert req is not None and req.years == 2

    def test_nombre_aberrant_ignore(self) -> None:
        assert extraire_annees("99 ans d'expérience") is None


class TestFormation:
    @pytest.mark.parametrize(
        ("texte", "niveau"),
        [
            ("Bac+5 ou équivalent", 5),
            ("Master en informatique", 5),
            ("Diplôme d'ingénieur", 5),
            ("Bac +3 minimum", 3),
            ("Licence ou Bachelor", 3),
            ("BTS ou DUT", 2),
            ("Doctorat", 8),
            ("Bac+3 à Bac+5", 3),
            ("Master's degree in computer science", 5),
        ],
    )
    def test_niveaux(self, texte: str, niveau: int) -> None:
        req = extraire_formation(texte)

        assert req is not None and req.level == niveau

    def test_formation_obligatoire_si_marqueur(self) -> None:
        req = extraire_formation("Bac+5 exigé")

        assert req is not None and req.mandatory is True

    def test_aucune_formation_citee(self) -> None:
        assert extraire_formation("Vous aimez les chiffres") is None

    def test_niveau_d_etudes_prend_le_plus_eleve(self) -> None:
        assert niveau_d_etudes("Licence puis Master 2") == 5
        assert niveau_d_etudes("Cuisinier confirmé") is None


class TestRubriques:
    def test_offre_francaise(self) -> None:
        req = extract_requirements(OFFRE_FR)

        assert req.has_requirement_section is True
        par_importance: dict[Importance, list[str]] = {}
        for ligne in req.lines:
            par_importance.setdefault(ligne.importance, []).append(ligne.text)

        assert (
            "Minimum 3 ans d'expérience en analyse de données"
            in par_importance[Importance.MANDATORY]
        )
        assert "Maîtrise de SQL et de Python" in par_importance[Importance.EXPECTED]
        assert "Esprit d'équipe et autonomie" in par_importance[Importance.EXPECTED]
        assert "Connaissance de Power BI souhaitée" in par_importance[Importance.OPTIONAL]
        assert "Notions de Docker appréciées" in par_importance[Importance.OPTIONAL]

    def test_les_missions_et_avantages_ne_sont_pas_des_exigences(self) -> None:
        req = extract_requirements(OFFRE_FR)

        textes = [ligne.text for ligne in req.lines]
        assert not any("tableaux de bord" in t for t in textes)
        assert not any("tickets restaurant" in t for t in textes)
        assert any("tableaux de bord" in ligne for ligne in req.body_lines)

    def test_offre_anglaise_rubrique_requirements_est_obligatoire(self) -> None:
        req = extract_requirements(OFFRE_EN)

        importances = {ligne.text: ligne.importance for ligne in req.lines}
        assert importances["Strong knowledge of Python, Spark and Airflow"] is Importance.MANDATORY
        assert importances["Kubernetes"] is Importance.OPTIONAL

    def test_les_valeurs_extraites_du_texte(self) -> None:
        fr = extract_requirements(OFFRE_FR)
        en = extract_requirements(OFFRE_EN)

        assert (fr.years.years, fr.years.mandatory) == (3, True)  # type: ignore[union-attr]
        assert fr.education is not None and fr.education.level == 5
        assert (en.years.years) == 5  # type: ignore[union-attr]
        assert en.education is not None and en.education.level == 5

    def test_offre_sans_rubriques(self) -> None:
        req = extract_requirements(OFFRE_SANS_STRUCTURE)

        assert req.has_requirement_section is False
        assert req.lines == ()
        assert req.years is None and req.education is None

    def test_un_marqueur_explicite_l_emporte_sur_la_rubrique(self) -> None:
        req = extract_requirements("Profil recherché\n- Anglais souhaité\n- SQL indispensable\n")

        assert [(ligne.text, ligne.importance) for ligne in req.lines] == [
            ("Anglais souhaité", Importance.OPTIONAL),
            ("SQL indispensable", Importance.MANDATORY),
        ]

    def test_une_phrase_longue_n_est_pas_un_titre(self) -> None:
        texte = (
            "Profil recherché\nVous avez une première expérience réussie en analyse de données.\n"
        )

        req = extract_requirements(texte)

        assert len(req.lines) == 1

    def test_puces_de_toute_forme_et_fins_de_ligne_windows(self) -> None:
        req = extract_requirements("Requirements\r\n• Python\r\n* SQL\r\n– Docker\r\n")

        assert [ligne.text for ligne in req.lines] == ["Python", "SQL", "Docker"]

    def test_texte_vide(self) -> None:
        req = extract_requirements("")

        assert (req.lines, req.body_lines, req.years, req.education) == ((), (), None, None)
