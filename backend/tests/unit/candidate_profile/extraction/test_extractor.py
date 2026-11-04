import pytest

from app.modules.candidate_profile.domain.extraction.dates import PartialDate
from app.modules.candidate_profile.domain.extraction.extractor import extract_profile
from app.modules.candidate_profile.domain.extraction.models import Confidence

from .cv_samples import CV_EN, CV_FR


class TestCoordonnees:
    def test_cv_francais(self) -> None:
        contact = extract_profile(CV_FR).contact

        assert contact.full_name == "Marie Dupont"
        assert contact.email == "marie.dupont@exemple.test"
        assert contact.phone == "+33 6 12 34 56 78"
        assert contact.city == "Lyon"
        assert contact.linkedin_url == "https://linkedin.com/in/marie-dupont"
        assert contact.website_url == "https://marie-dupont.exemple.test"

    def test_cv_anglais(self) -> None:
        contact = extract_profile(CV_EN).contact

        assert contact.full_name == "John Smith"
        assert contact.email == "john.smith@example.test"
        assert contact.phone == "(415) 555-0132"
        assert contact.city is None  # pas de code postal : la ville n'est pas devinée

    def test_aucune_coordonnee_dans_le_texte_donne_des_none(self) -> None:
        contact = extract_profile("Quelque chose\nsans rien d'utile").contact

        assert (contact.email, contact.phone, contact.linkedin_url, contact.website_url) == (
            None,
            None,
            None,
            None,
        )

    @pytest.mark.parametrize("ligne", ["CURRICULUM VITAE", "Développeur Python senior", "CV 2024"])
    def test_une_premiere_ligne_qui_n_est_pas_un_nom_n_est_pas_prise_pour_un_nom(
        self, ligne: str
    ) -> None:
        # « Développeur Python senior » a trois mots mais « Python senior » ressemble à un nom :
        # le titre seul ne doit pas être pris pour une identité si une autre ligne suit.
        nom = extract_profile(f"{ligne}\n\nEXPÉRIENCE\n").contact.full_name

        assert nom in (None, "Développeur Python senior")
        assert nom != "CURRICULUM VITAE"
        assert nom != "CV 2024"

    def test_une_periode_n_est_pas_un_telephone(self) -> None:
        contact = extract_profile("Marie Dupont\n2018 2019 2020 2021\n").contact

        assert contact.phone is None


class TestExperiences:
    def test_cv_francais_deux_experiences(self) -> None:
        experiences = extract_profile(CV_FR).experiences

        assert len(experiences) == 2
        courante, ancienne = experiences

        assert courante.title == "Développeuse Python"
        assert courante.company == "Exemple SA"
        assert courante.start == PartialDate(2021, 1)
        assert courante.end is None
        assert courante.is_current is True
        assert courante.achievements == (
            "Conception d'API REST pour 50 000 utilisateurs",
            "Migration vers PostgreSQL sans interruption de service",  # ligne coupée recollée
        )
        assert courante.confidence is Confidence.HIGH

        assert ancienne.title == "Analyste de données"
        assert ancienne.company == "Acme"
        assert (ancienne.start, ancienne.end) == (PartialDate(2018, 3), PartialDate(2020, 12))
        assert ancienne.description == "Mise en place du reporting mensuel."
        assert ancienne.achievements == ("Tableaux de bord Power BI",)

    def test_cv_anglais_organisation_avant_l_intitule(self) -> None:
        experiences = extract_profile(CV_EN).experiences

        assert [(e.title, e.company) for e in experiences] == [
            ("Senior Data Engineer", "Acme Corp"),
            ("Data Analyst", "Beta Ltd"),
        ]
        assert experiences[0].is_current

    def test_chaque_element_garde_son_texte_source(self) -> None:
        for experience in extract_profile(CV_FR).experiences:
            assert experience.source_text
            assert experience.title is not None
            assert experience.title in experience.source_text

    def test_une_ambiguite_est_signalee_en_confiance_basse(self) -> None:
        texte = "EXPÉRIENCE\nAlpha\nBeta\n2020 - 2022\n- Mission\n"

        (experience,) = extract_profile(texte).experiences

        assert experience.confidence is Confidence.LOW

    def test_une_annee_seule_n_est_pas_une_experience(self) -> None:
        texte = "EXPÉRIENCE\nConsultant chez Acme\n2020\n- Projet\n"

        assert extract_profile(texte).experiences == ()

    def test_date_seule_sur_sa_ligne_intitule_et_entreprise_en_dessous(self) -> None:
        texte = "EXPÉRIENCE\n2019 - 2021\nIngénieur logiciel\nAcme\n- Mission\n"

        (experience,) = extract_profile(texte).experiences

        assert (experience.title, experience.company) == ("Ingénieur logiciel", "Acme")

    def test_tout_sur_une_ligne(self) -> None:
        texte = "EXPÉRIENCE\nChef de projet chez Acme 2019 - 2021\n- Mission\n"

        (experience,) = extract_profile(texte).experiences

        assert (experience.title, experience.company) == ("Chef de projet", "Acme")
        assert experience.start == PartialDate(2019)

    def test_ne_prend_pas_une_puce_datee_pour_une_experience(self) -> None:
        texte = "EXPÉRIENCE\nDéveloppeur chez Acme\n2019 - 2021\n- Migration 2020 - 2021\n"

        assert len(extract_profile(texte).experiences) == 1


class TestFormations:
    def test_cv_francais(self) -> None:
        formations = extract_profile(CV_FR).educations

        assert len(formations) == 2
        master, licence = formations
        assert master.degree == "Master Informatique"
        assert master.institution == "Université de Lyon"
        assert (master.start, master.end) == (PartialDate(2016), PartialDate(2018))
        assert master.confidence is Confidence.HIGH
        assert licence.degree == "Licence Mathématiques"
        assert licence.institution == "Université Claude Bernard"

    def test_une_annee_seule_est_la_fin_des_etudes(self) -> None:
        (formation,) = extract_profile("FORMATION\nMBA Management - HEC School\n2019\n").educations

        assert formation.start is None
        assert formation.end == PartialDate(2019)

    def test_cv_anglais_diplome_et_etablissement_sur_la_meme_ligne(self) -> None:
        (formation,) = extract_profile(CV_EN).educations

        assert formation.degree == "BSc Computer Science"
        assert formation.institution == "University of Leeds"


class TestCompetences:
    def test_listes_categories_puces_et_doublons(self) -> None:
        competences = extract_profile(CV_FR).skills

        assert [(c.name, c.category) for c in competences] == [
            ("Python", "Langages"),
            ("SQL", "Langages"),
            ("TypeScript", "Langages"),
            ("Docker", "Outils"),
            ("Git", "Outils"),
            ("Linux", "Outils"),
            ("PostgreSQL", None),
        ]  # « Python » répété à la fin n'est pas dupliqué

    def test_une_phrase_n_est_pas_decoupee_en_competences(self) -> None:
        phrase = "J'ai travaillé pendant de longues années sur de gros projets de données"
        texte = f"COMPÉTENCES\n{phrase}\nSQL\n"

        assert [c.name for c in extract_profile(texte).skills] == ["SQL"]


class TestLangues:
    def test_cv_francais(self) -> None:
        langues = extract_profile(CV_FR).languages

        assert [(lg.language_code, lg.proficiency) for lg in langues] == [
            ("fr", "native"),
            ("en", "b2"),
            ("es", None),
        ]
        espagnol = langues[2]
        assert espagnol.level_text == "notions scolaires"

    def test_plusieurs_langues_sur_une_ligne(self) -> None:
        langues = extract_profile(CV_EN).languages

        assert [(lg.language_code, lg.proficiency) for lg in langues] == [
            ("en", "native"),
            ("fr", "b1"),
        ]

    @pytest.mark.parametrize("niveau", ["courant", "fluent", "intermédiaire", "bon niveau"])
    def test_un_niveau_vague_n_est_jamais_converti_en_niveau_cecr(self, niveau: str) -> None:
        (langue,) = extract_profile(f"LANGUES\nAnglais ({niveau})\n").languages

        assert langue.proficiency is None
        assert langue.level_text == niveau

    def test_une_langue_inconnue_est_ignoree(self) -> None:
        assert extract_profile("LANGUES\nKlingon (C2)\n").languages == ()

    def test_une_phrase_n_est_pas_une_langue(self) -> None:
        assert extract_profile("LANGUES\nParle couramment l'anglais\n").languages == ()


class TestCertifications:
    def test_nom_et_annee(self) -> None:
        certifs = extract_profile(CV_FR).certifications

        assert [(c.name, c.year) for c in certifs] == [
            ("AWS Certified Cloud Practitioner", 2022),
            ("Scrum Master (PSM I)", None),
        ]


class TestGlobal:
    def test_resume(self) -> None:
        assert extract_profile(CV_FR).summary == (
            "Développeuse backend avec six ans d'expérience. Passionnée par la qualité logicielle."
        )

    def test_les_sections_ignorees_ne_polluent_pas_les_autres(self) -> None:
        profil = extract_profile(CV_FR)

        assert all("Randonnée" not in c.name for c in profil.certifications)
        assert all("Randonnée" not in lg.name for lg in profil.languages)

    def test_un_texte_sans_structure_donne_un_profil_vide_et_des_avertissements(self) -> None:
        profil = extract_profile("Du texte libre\nsans aucun titre de section.")

        assert (profil.experiences, profil.educations, profil.skills) == ((), (), ())
        assert len(profil.warnings) == 3

    def test_une_section_presente_mais_illisible_est_signalee(self) -> None:
        profil = extract_profile("EXPÉRIENCE\nJ'ai beaucoup travaillé\nsans donner de dates.\n")

        assert profil.experiences == ()
        assert any("expérience" in w and "à la main" in w for w in profil.warnings)

    def test_aucune_donnee_inventee_sur_un_cv_minimal(self) -> None:
        profil = extract_profile("EXPÉRIENCE\nConsultant\n2020 - 2021\n")

        (experience,) = profil.experiences
        assert experience.company is None
        assert experience.location is None
        assert experience.description is None
        assert experience.achievements == ()

    def test_texte_vide(self) -> None:
        profil = extract_profile("")

        assert profil.contact.email is None
        assert profil.experiences == ()
