"""Analyse déterministe d'une offre : missions, langues, mobilité, manques, résumé."""

from decimal import Decimal

from app.modules.job_intelligence.domain.analysis.extraction import (
    analyze_offer,
    extract_languages,
    extract_missions,
    extract_mobility,
    extractive_summary,
)
from app.modules.job_intelligence.domain.analysis.models import MissingInfo, VisaPolicy
from app.modules.job_intelligence.domain.matching.models import OfferFacts

OFFRE_FR = """Développeur Python confirmé

Nous construisons une plateforme de données utilisée par des milliers d'entreprises. Rejoignez une équipe passionnée au cœur de Paris.

Vos missions
- Concevoir et maintenir des API FastAPI
- Écrire des requêtes SQL performantes sur PostgreSQL
- Participer aux revues de code

Compétences requises
- 3 ans d'expérience minimum en Python
- Maîtrise de Docker
- Anglais courant exigé

Un plus
- Connaissance de Kubernetes

Avantages
- Aide à la relocalisation possible
- Déplacements occasionnels (10 %)
"""


def offre(description: str = OFFRE_FR, **champs: object) -> OfferFacts:
    base: dict[str, object] = {
        "title": "Développeur Python",
        "description": description,
        "location": "Paris, France",
        "country_code": "FR",
        "employment_type": "permanent",
        "remote_type": "hybrid",
        "salary_min": None,
        "salary_max": None,
        "salary_currency": None,
        "published_at": None,
    }
    base.update(champs)
    return OfferFacts(**base)  # type: ignore[arg-type]


class TestMissions:
    def test_lit_uniquement_la_rubrique_missions(self) -> None:
        assert extract_missions(OFFRE_FR) == (
            "Concevoir et maintenir des API FastAPI",
            "Écrire des requêtes SQL performantes sur PostgreSQL",
            "Participer aux revues de code",
        )

    def test_sans_rubrique_aucune_mission_n_est_inventee(self) -> None:
        assert extract_missions("Nous cherchons quelqu'un de motivé.\nPoste à pourvoir.") == ()

    def test_rubrique_anglaise(self) -> None:
        texte = "What you'll do\n* Build pipelines\n* Review PRs\nRequirements\n* Python"

        assert extract_missions(texte) == ("Build pipelines", "Review PRs")


class TestLangues:
    def test_langue_avec_niveau_et_obligation(self) -> None:
        langues = extract_languages("Anglais courant exigé\nFrançais : B2 minimum")

        par_code = {x.language: x for x in langues}
        assert (par_code["en"].level, par_code["en"].mandatory) == ("courant", True)
        assert par_code["fr"].level == "B2"

    def test_une_simple_mention_n_est_pas_une_exigence(self) -> None:
        assert extract_languages("Bureaux à Paris, France\nUne équipe anglophone") == ()

    def test_langue_souhaitee_n_est_pas_obligatoire(self) -> None:
        (allemand,) = extract_languages("Allemand courant apprécié")

        assert allemand.language == "de" and allemand.mandatory is False

    def test_anglais(self) -> None:
        (anglais,) = extract_languages("You are fluent in English and enjoy writing")

        assert anglais.language == "en" and anglais.level == "fluent"


class TestMobilite:
    def test_sponsoring_propose(self) -> None:
        m = extract_mobility("We offer visa sponsorship is available for the right candidate")

        assert m.visa is VisaPolicy.SPONSORSHIP_OFFERED

    def test_refus_de_sponsoring_l_emporte(self) -> None:
        m = extract_mobility("Unfortunately we cannot offer visa sponsorship for this role.")

        assert m.visa is VisaPolicy.NO_SPONSORSHIP

    def test_autorisation_de_travail_requise(self) -> None:
        m = extract_mobility("Vous devez disposer d'une autorisation de travail en France.")

        assert m.visa is VisaPolicy.WORK_AUTHORIZATION_REQUIRED

    def test_relocation_et_deplacements(self) -> None:
        m = extract_mobility(OFFRE_FR)

        assert m.relocation_offered is True
        assert m.travel is not None and "10 %" in m.travel
        assert m.visa is None  # rien n'est dit : inconnu, pas « non »

    def test_texte_neutre_donne_une_mobilite_vide(self) -> None:
        assert extract_mobility("Équipe sympa, bureaux lumineux.").is_empty


class TestResume:
    def test_extractif_phrases_de_l_annonce_sans_reformulation(self) -> None:
        resume = extractive_summary(OFFRE_FR)

        assert resume is not None
        assert resume.startswith("Nous construisons une plateforme de données")
        assert resume in OFFRE_FR  # rien d'ajouté : une citation

    def test_texte_trop_court_pas_de_resume(self) -> None:
        assert extractive_summary("Poste de dev.") is None


class TestAnalyseComplete:
    def test_exemple_francais(self) -> None:
        a = analyze_offer(offre())

        assert a.years_experience == 3 and a.years_mandatory is True
        assert "Docker" in a.mandatory_skills
        assert "Kubernetes" in a.desired_skills
        assert {"FastAPI", "PostgreSQL"} <= set(a.technologies)
        assert a.languages[0].language == "en"
        assert MissingInfo.SALARY in a.missing
        assert MissingInfo.LOCATION not in a.missing

    def test_signale_ce_que_l_offre_ne_dit_pas(self) -> None:
        a = analyze_offer(
            offre(
                "Poste de développeur.",
                location=None,
                country_code=None,
                employment_type=None,
                remote_type=None,
            )
        )

        assert set(a.missing) >= {
            MissingInfo.LOCATION,
            MissingInfo.EMPLOYMENT_TYPE,
            MissingInfo.REMOTE,
            MissingInfo.EXPERIENCE,
            MissingInfo.REQUIREMENTS,
            MissingInfo.MISSIONS,
        }

    def test_un_salaire_connu_n_est_pas_manquant(self) -> None:
        a = analyze_offer(offre(salary_min=Decimal(40000), salary_currency="EUR"))

        assert MissingInfo.SALARY not in a.missing

    def test_serialisation_json_stable(self) -> None:
        d = analyze_offer(offre()).to_dict()

        assert d["version"] == "a2"
        assert d["mobility"]["relocation_offered"] is True
        assert {"code": "salary", "label": "Salaire non indiqué"} in d["missing"]
        assert d == analyze_offer(offre()).to_dict()  # déterministe


class TestTechnologies:
    def test_ne_confond_pas_un_mot_courant_avec_une_technologie(self) -> None:
        texte = (
            "We go to market fast, the rest of the team is remote and we spring into action. "
            "Ability to express ideas. R&D department."
        )

        assert analyze_offer(offre(texte)).technologies == ()

    def test_releve_les_technologies_connues_dans_toute_l_annonce(self) -> None:
        texte = "Stack : Python, FastAPI, PostgreSQL et Docker sur AWS. Un plus : Golang, C++."

        assert analyze_offer(offre(texte)).technologies == (
            "Python",
            "Golang",
            "C++",
            "FastAPI",
            "PostgreSQL",
            "AWS",
            "Docker",
        )


class TestBruitDesAnnoncesReelles:
    def test_la_prose_des_rubriques_d_exigences_n_est_pas_affichee_comme_competence(self) -> None:
        texte = (
            "Requirements\n"
            "- Applicant must be available 9am-12pm CET\n"
            "- About Datadog and Computer Science background\n"
            "- Experience with Python, SQL, AWS and Node.js\n"
        )

        a = analyze_offer(offre(texte))

        assert set(a.mandatory_skills + a.expected_skills) == {"Python", "SQL", "AWS", "Node.js"}

    def test_les_pratiques_courantes_sont_reconnues(self) -> None:
        a = analyze_offer(offre("Stack : Machine Learning, CI/CD, Scrum et Kubernetes."))

        assert {"Machine Learning", "CI/CD", "Scrum", "Kubernetes"} <= set(a.technologies)
