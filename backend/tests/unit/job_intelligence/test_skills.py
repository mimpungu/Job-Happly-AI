from decimal import Decimal
from typing import ClassVar

import pytest

from app.modules.job_intelligence.domain.matching.models import MatchKind, Status
from app.modules.job_intelligence.domain.matching.offer_requirements import (
    Importance,
    extract_requirements,
)
from app.modules.job_intelligence.domain.matching.skills import (
    canonique,
    evaluate_skills,
    extract_terms,
    match_term,
    skills_in_text,
)

from .factories import profil
from .offers import OFFRE_EN, OFFRE_FR


class TestExtractionDesTermes:
    @pytest.mark.parametrize(
        ("ligne", "attendu"),
        [
            ("Maîtrise de SQL et de Python", ["SQL", "Python"]),
            ("Strong knowledge of Python, Spark and Airflow", ["Python", "Spark", "Airflow"]),
            ("Connaissance de Power BI souhaitée", ["Power BI"]),
            ("Expérience avec C++ et C#", ["C++", "C#"]),
            ("Node.js, .NET, Python3", ["Node.js", ".NET", "Python3"]),
            ("Kubernetes", ["Kubernetes"]),
            ("Docker / Git / AWS", ["Docker", "Git", "AWS"]),
        ],
    )
    def test_reconnait_les_competences(self, ligne: str, attendu: list[str]) -> None:
        assert extract_terms(ligne) == attendu

    @pytest.mark.parametrize(
        "ligne",
        [
            "Esprit d'équipe et autonomie",
            "Bac+5 ou équivalent",
            "Minimum 3 ans d'expérience en analyse de données",
            "CDI à temps plein, H/F",
            "Vous avez une bonne capacité d'organisation",
            "Master en informatique",
        ],
    )
    def test_ne_prend_pas_la_prose_pour_des_competences(self, ligne: str) -> None:
        assert extract_terms(ligne) == []

    def test_une_phrase_sans_enumeration_ne_livre_pas_de_mot_capitalise(self) -> None:
        ligne = "Vous interviendrez chez Danone auprès des équipes commerciales de la région"

        assert extract_terms(ligne) == []

    def test_en_mode_strict_les_mots_capitalises_sont_ignores(self) -> None:
        assert extract_terms("Python, Docker et SQL", strict=True) == ["SQL"]

    def test_les_sigles_de_contrat_sont_ignores(self) -> None:
        assert extract_terms("CDI, CDD ou RH") == []


class TestCorrespondance:
    index: ClassVar[dict[str, str]] = {
        canonique(n): n for n in ("PostgreSQL", "Python", "Microsoft Power BI", "JavaScript")
    }

    @pytest.mark.parametrize(
        ("terme", "kind", "nom"),
        [
            ("Python", MatchKind.PRESENT, "Python"),
            ("python", MatchKind.PRESENT, "Python"),
            ("Postgres", MatchKind.PRESENT, "PostgreSQL"),  # synonyme
            ("JS", MatchKind.PRESENT, "JavaScript"),
            ("Power BI", MatchKind.PRESENT, "Microsoft Power BI"),  # séquence de mots
            ("MySQL", MatchKind.PARTIAL, "PostgreSQL"),  # même famille
            ("Tableau", MatchKind.ABSENT, None),
            ("Java", MatchKind.ABSENT, None),  # Java n'est pas JavaScript
            ("C", MatchKind.ABSENT, None),
        ],
    )
    def test_statuts(self, terme: str, kind: MatchKind, nom: str | None) -> None:
        assert match_term(terme, self.index) == (kind, nom)

    def test_c_plus_plus_n_est_pas_c(self) -> None:
        assert canonique("C++") != canonique("C")
        assert canonique("C#") != canonique("C")

    def test_competences_citees_dans_un_texte_mot_entier(self) -> None:
        trouvees = skills_in_text(
            ("SQL", "Java", "C", "R"), "Nous utilisons JavaScript et sql, pas de R&D"
        )

        assert trouvees == ["SQL"]  # Java ⊄ JavaScript, « C » et « R » ne sont pas des mots ici


class TestCritereCompetences:
    def test_offre_francaise_quatre_etats(self) -> None:
        req = extract_requirements(OFFRE_FR)

        analyse = evaluate_skills(profil(), req, Decimal(25))

        etats = {t.label: t.kind for t in analyse.terms}
        assert etats["SQL"] is MatchKind.PRESENT
        assert etats["Python"] is MatchKind.PRESENT
        assert etats["Power BI"] is MatchKind.ABSENT
        assert etats["Docker"] is MatchKind.ABSENT
        assert analyse.unverifiable == ("Esprit d'équipe et autonomie",)
        assert analyse.result.status is Status.EVALUATED
        kinds = {i.kind for i in analyse.result.items}
        assert MatchKind.UNVERIFIABLE in kinds

    def test_une_exigence_non_verifiable_ne_pese_pas_dans_le_score(self) -> None:
        avec = extract_requirements("Profil recherché\n- SQL\n- Esprit d'équipe\n")
        sans = extract_requirements("Profil recherché\n- SQL\n")

        a = evaluate_skills(profil(), avec, Decimal(1)).result.score
        b = evaluate_skills(profil(), sans, Decimal(1)).result.score

        assert a == b == Decimal(1)

    def test_une_competence_obligatoire_absente_pese_plus_qu_une_optionnelle(self) -> None:
        obligatoire_absente = extract_requirements(
            "Requirements\n- SQL\n- Tableau\nNice to have\n- Python\n"
        )
        optionnelle_absente = extract_requirements(
            "Requirements\n- SQL\n- Python\nNice to have\n- Tableau\n"
        )

        a = evaluate_skills(profil(), obligatoire_absente, Decimal(1)).result.score
        b = evaluate_skills(profil(), optionnelle_absente, Decimal(1)).result.score

        assert a is not None and b is not None and a < b

    def test_correspondance_partielle_vaut_la_moitie(self) -> None:
        req = extract_requirements("Profil recherché\n- MySQL\n")

        resultat = evaluate_skills(profil(skills=("PostgreSQL",)), req, Decimal(1)).result

        assert resultat.score == Decimal("0.5")
        assert resultat.items[0].kind is MatchKind.PARTIAL

    def test_profil_sans_competence_donnees_manquantes_pas_zero(self) -> None:
        resultat = evaluate_skills(
            profil(skills=()), extract_requirements(OFFRE_FR), Decimal(25)
        ).result

        assert resultat.status is Status.MISSING_DATA
        assert resultat.score is None

    def test_offre_sans_competence_identifiable_donnees_manquantes(self) -> None:
        req = extract_requirements("Profil recherché\n- Esprit d'équipe\n- Rigueur\n")

        resultat = evaluate_skills(profil(), req, Decimal(25)).result

        assert resultat.status is Status.MISSING_DATA

    def test_offre_sans_rubrique_utilise_sigles_et_competences_du_profil(self) -> None:
        req = extract_requirements("Vous analyserez les données avec SQL et Excel sur AWS.")

        analyse = evaluate_skills(profil(), req, Decimal(1))

        etats = {t.label: (t.kind, t.importance) for t in analyse.terms}
        assert etats["SQL"] == (MatchKind.PRESENT, Importance.MENTIONED)
        assert etats["Excel"] == (MatchKind.PRESENT, Importance.MENTIONED)
        assert etats["AWS"] == (MatchKind.ABSENT, Importance.MENTIONED)

    def test_avec_rubrique_une_mention_hors_exigences_n_invente_pas_de_manque(self) -> None:
        req = extract_requirements("Missions\n- Utiliser Tableau et AWS\nProfil recherché\n- SQL\n")

        analyse = evaluate_skills(profil(), req, Decimal(1))

        assert {t.label for t in analyse.terms} == {"SQL"}

    def test_anglais(self) -> None:
        analyse = evaluate_skills(
            profil(skills=("Python", "Spark")), extract_requirements(OFFRE_EN), Decimal(1)
        )

        etats = {t.label: t.kind for t in analyse.terms}
        assert etats["Python"] is MatchKind.PRESENT
        assert etats["Spark"] is MatchKind.PRESENT
        assert etats["Airflow"] is MatchKind.PARTIAL or etats["Airflow"] is MatchKind.ABSENT
        assert etats["Kubernetes"] is MatchKind.ABSENT

    def test_l_explication_rappelle_qu_absent_ne_veut_pas_dire_incompetent(self) -> None:
        resultat = evaluate_skills(profil(), extract_requirements(OFFRE_FR), Decimal(1)).result

        assert "pas forcément absente chez vous" in resultat.explanation
