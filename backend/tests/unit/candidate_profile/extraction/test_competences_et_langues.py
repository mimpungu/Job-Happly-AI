"""Compétences et langues d'un CV à colonne latérale : libellés, lignes coupées, niveaux."""

from app.modules.candidate_profile.domain.extraction.extractor import extract_profile
from app.modules.candidate_profile.domain.extraction.languages import extract_languages
from app.modules.candidate_profile.domain.extraction.skills import extract_skills


def _noms(lignes: list[str]) -> list[str]:
    return [s.name for s in extract_skills(tuple(lignes))]


def _par_categorie(lignes: list[str]) -> list[tuple[str, str | None]]:
    return [(s.name, s.category) for s in extract_skills(tuple(lignes))]


class TestLangues:
    def test_le_niveau_d_une_langue_repetee_sur_une_ligne_a_part_est_retenu(self) -> None:
        # Le PDF donne « Français » puis « Français - C2 » : le niveau ne doit pas être perdu.
        langues = extract_languages(("Français", "Français - C2", "Anglais", "Anglais - A2"))

        assert [(lg.name, lg.proficiency) for lg in langues] == [
            ("Français", "c2"),
            ("Anglais", "a2"),
        ]

    def test_une_langue_sans_niveau_reste_sans_niveau(self) -> None:
        langues = extract_languages(("Français", "Anglais"))

        assert [lg.proficiency for lg in langues] == [None, None]


class TestLibellesDeCategories:
    def test_un_libelle_se_terminant_par_deux_points_n_est_pas_une_competence(self) -> None:
        assert _par_categorie(["Conception et Modélisation :", "Mérise, UML"]) == [
            ("Mérise", "Conception et Modélisation"),
            ("UML", "Conception et Modélisation"),
        ]

    def test_un_libelle_coupe_sur_deux_lignes_est_recolle(self) -> None:
        lignes = ["Outils de Gestion de", "Projet :", "Confluence, Jira"]

        assert _par_categorie(lignes) == [
            ("Confluence", "Outils de Gestion de Projet"),
            ("Jira", "Outils de Gestion de Projet"),
        ]

    def test_un_titre_coupe_sans_deux_points_est_reconnu(self) -> None:
        lignes = ["Langages de", "Programmation", "C, C++, Python"]

        assert _par_categorie(lignes) == [
            ("C", "Langages de Programmation"),
            ("C++", "Langages de Programmation"),
            ("Python", "Langages de Programmation"),
        ]

    def test_un_titre_coupe_apres_une_liste_qui_finit_par_une_virgule_est_reconnu(self) -> None:
        # Le CV écrit « SCRUM, » puis ouvre une nouvelle catégorie sur deux lignes.
        lignes = ["Trello,", "SCRUM,", "Langages de", "Programmation", "C, Python"]

        assert _par_categorie(lignes) == [
            ("Trello", None),
            ("SCRUM", None),
            ("C", "Langages de Programmation"),
            ("Python", "Langages de Programmation"),
        ]

    def test_un_titre_sans_deux_points_suivi_d_une_liste_est_reconnu(self) -> None:
        lignes = ["Systèmes et Réseaux", "Windows, Linux", "Logiciels", "VS Code, Figma"]

        assert _par_categorie(lignes) == [
            ("Windows", "Systèmes et Réseaux"),
            ("Linux", "Systèmes et Réseaux"),
            ("VS Code", "Logiciels"),
            ("Figma", "Logiciels"),
        ]

    def test_une_liste_verticale_n_est_jamais_prise_pour_des_titres(self) -> None:
        # Le seul cas où perdre une ligne serait invisible : on garde chaque ligne.
        assert _noms(["Python", "Gestion de projet", "SQL"]) == [
            "Python",
            "Gestion de projet",
            "SQL",
        ]


class TestLignesCoupees:
    def test_une_liste_coupee_apres_une_virgule_est_recollee(self) -> None:
        lignes = ["Confluence, Jira, Trello,", "Méthodologies Agile,", "SCRUM,"]

        assert _noms(lignes) == ["Confluence", "Jira", "Trello", "Méthodologies Agile", "SCRUM"]

    def test_deux_listes_a_virgules_consecutives_ne_sont_pas_fusionnees(self) -> None:
        # Sans signal explicite, « SQL » et « Jira » ne forment pas une seule compétence.
        assert _noms(["Python, SQL", "Jira, Docker"]) == ["Python", "SQL", "Jira", "Docker"]

    def test_une_parenthese_n_est_pas_coupee_et_ses_elements_sont_des_competences(self) -> None:
        lignes = ["Windows All Version, Linux", "(Ubuntu, Debian, Kali,", "Mandriva), MacOS"]

        assert _noms(lignes) == [
            "Windows All Version",
            "Linux",
            "Ubuntu",
            "Debian",
            "Kali",
            "Mandriva",
            "MacOS",
        ]

    def test_une_parenthese_sans_liste_reste_dans_le_nom(self) -> None:
        assert _noms(["Excel (avancé), Word"]) == ["Excel (avancé)", "Word"]

    def test_une_liste_verticale_dont_une_ligne_a_une_virgule_n_est_pas_recollee(self) -> None:
        lignes = ["Rigoureux", "Travail en équipe", "Autonomie, Curieux", "Aisance relationnelle"]

        assert _noms(lignes) == [
            "Rigoureux",
            "Travail en équipe",
            "Autonomie",
            "Curieux",
            "Aisance relationnelle",
        ]


def test_la_section_atouts_est_lue_comme_des_competences() -> None:
    texte = "Marie Dupont\n\nATOUTS\nRigoureux\nCurieux\n\nLANGUES\nFrançais - C2\n"

    profil = extract_profile(texte)

    assert [s.name for s in profil.skills] == ["Rigoureux", "Curieux"]
    assert [(lg.name, lg.proficiency) for lg in profil.languages] == [("Français", "c2")]
