"""Générateur, retours, sélection de simulation et brouillon de relance (EPIC 016)."""

from datetime import timedelta

import pytest

from app.modules.interview_preparation.domain.enums import (
    InterviewStage,
    QuestionCategory,
)
from app.modules.interview_preparation.domain.feedback import evaluate_answer
from app.modules.interview_preparation.domain.followup import (
    draft_follow_up,
    suggest_follow_up_date,
)
from app.modules.interview_preparation.domain.generator import build_preparation
from app.modules.interview_preparation.domain.models import InterviewData, Question
from app.modules.interview_preparation.domain.simulation import select_questions, summarize
from app.modules.interview_preparation.domain.text import mentions, norm, numbers
from tests.unit.interview_preparation.support import NOW, offre, profil


class TestTexte:
    def test_norm_ignore_accents_casse_et_apostrophe_typographique(self) -> None:
        assert norm("  Développeur   J\u2019ai ") == "developpeur j'ai"

    def test_mention_en_mot_entier(self) -> None:
        assert mentions("Expert JavaScript", "JavaScript")
        assert not mentions("Expert JavaScript", "Java")
        assert mentions("Stack C++ et C#", "C++")

    def test_nombres(self) -> None:
        assert numbers("12 services, 3,5 M€") == {"12", "3.5"}


class TestPreparation:
    def test_questions_par_categorie_et_adaptees_au_poste(self) -> None:
        contenu = build_preparation(profil(), offre())

        categories = {q.category for q in contenu.questions}
        assert categories == set(QuestionCategory)
        assert any("Ingénieur Backend" in q.text and "Acme" in q.text for q in contenu.questions)
        assert len({q.id for q in contenu.questions}) == len(contenu.questions)

    def test_competences_possedees_vs_manquantes_jamais_inventees(self) -> None:
        contenu = build_preparation(profil(), offre())

        assert contenu.skills_matched == ("Python", "FastAPI")
        assert contenu.skills_to_prepare == ("Kubernetes",)
        ecarts = [q for q in contenu.questions if q.skill_gap]
        assert [q.skill for q in ecarts] == ["Kubernetes"]
        # une question « cas concret » n'existe que pour une compétence réellement possédée
        concrets = [q.skill for q in contenu.questions if q.skill and not q.skill_gap]
        assert "Kubernetes" not in concrets

    def test_presentation_composee_de_faits_du_profil(self) -> None:
        contenu = build_preparation(profil(), offre())

        assert "Camille Dubois" in contenu.pitch
        assert "Ingénieure Backend chez OpenCorp depuis 2021" in contenu.pitch
        assert "Python, FastAPI" in contenu.pitch
        assert "Kubernetes" not in contenu.pitch
        assert contenu.pitch_to_complete  # la motivation personnelle reste à écrire

    def test_experiences_classees_par_recoupement_avec_l_offre(self) -> None:
        contenu = build_preparation(profil(), offre(required_skills=("Java",)))

        assert contenu.highlights[0].experience_label == "Développeuse — Vieille Boîte"
        assert contenu.highlights[0].matched_terms == ("Java",)

    def test_trames_basees_sur_le_vrai_parcours_resultat_a_completer(self) -> None:
        profile = profil()
        contenu = build_preparation(profile, offre())

        reelles = {a for e in profile.experiences for a in e.achievements}
        assert contenu.answers
        for trame in contenu.answers:
            assert set(trame.actions) <= reelles | {e.description for e in profile.experiences}
            assert trame.result is None  # jamais de résultat inventé
            assert trame.to_complete

    def test_trame_technique_adossee_a_l_experience_qui_cite_la_competence(self) -> None:
        contenu = build_preparation(profil(), offre(required_skills=("Java",)))
        technique = next(q for q in contenu.questions if q.skill == "Java")

        trame = next(t for t in contenu.answers if t.question_id == technique.id)

        assert trame.experience_label == "Développeuse — Vieille Boîte"
        assert trame.actions == ("Maintenance d'applications Java",)

    def test_questions_pour_le_recruteur_citent_la_stack(self) -> None:
        contenu = build_preparation(profil(), offre())

        assert any("Python" in q for q in contenu.recruiter_questions)
        assert len(contenu.recruiter_questions) >= 5

    def test_avertissements_offre_pauvre_et_profil_sans_experience(self) -> None:
        vide = profil().model_copy(update={"experiences": ()})
        contenu = build_preparation(vide, offre(description="", required_skills=()))

        assert len(contenu.warnings) == 3
        assert contenu.answers == ()
        assert contenu.highlights == ()

    def test_version_anglaise(self) -> None:
        contenu = build_preparation(profil(), offre(), language="en")

        assert contenu.questions[0].text == "Tell me about yourself."
        assert "My name is Camille Dubois." in contenu.pitch
        assert "since 2021" in contenu.pitch

    def test_generation_deterministe(self) -> None:
        assert build_preparation(profil(), offre()) == build_preparation(profil(), offre())


def _question(**kw: object) -> Question:
    base = {
        "id": "technical-1",
        "category": QuestionCategory.TECHNICAL,
        "text": "Décrivez un cas avec Python.",
        "rationale": "x",
        "skill": "Python",
    }
    return Question(**{**base, **kw})


BONNE_REPONSE = (
    "Dans mon poste chez OpenCorp, j'ai migré 12 services vers FastAPI en Python. "
    "Ce qui a permis de réduire la dette technique. " + "Nous avons travaillé en équipe. " * 4
)


class TestRetours:
    def test_bonne_reponse_structuree(self) -> None:
        retour = evaluate_answer(
            _question(), BONNE_REPONSE, offer_terms=("Python",), known_numbers={"12"}
        )

        assert retour.score >= 85
        assert retour.unverified_numbers == ()
        assert any("Situation, Action, Résultat" in f for f in retour.strengths)

    def test_reponse_vide_de_contenu_est_faible_et_guidee(self) -> None:
        retour = evaluate_answer(
            _question(), "Je ne sais pas.", offer_terms=("Python",), known_numbers=set()
        )

        assert retour.score < 40
        assert any("très courte" in p for p in retour.improvements)

    def test_chiffre_absent_du_parcours_est_signale_pas_valide(self) -> None:
        retour = evaluate_answer(
            _question(),
            BONNE_REPONSE.replace("12", "400"),
            offer_terms=("Python",),
            known_numbers={"12"},
        )

        assert retour.unverified_numbers == ("400",)
        assert any("Vérifiez" in p for p in retour.improvements)

    def test_reponse_trop_longue(self) -> None:
        retour = evaluate_answer(_question(), "mot " * 300, offer_terms=(), known_numbers=set())

        assert any("longue" in p for p in retour.improvements)

    def test_score_borne(self) -> None:
        retour = evaluate_answer(_question(), BONNE_REPONSE, offer_terms=(), known_numbers={"12"})

        assert 0 <= retour.score <= 100


class TestSimulation:
    def test_selection_alternee_deterministe_et_ecarts_en_dernier(self) -> None:
        questions = build_preparation(profil(), offre()).questions

        choisies = select_questions(questions, 6)

        assert [q.category for q in choisies[:3]] == [
            QuestionCategory.HR,
            QuestionCategory.BEHAVIORAL,
            QuestionCategory.TECHNICAL,
        ]
        assert choisies == select_questions(questions, 6)
        assert len(choisies) == 6
        gap = next(q for q in questions if q.skill_gap)
        assert gap not in select_questions(questions, 6)  # reste après les compétences possédées

    def test_selection_plafonnee_au_nombre_de_questions(self) -> None:
        questions = build_preparation(profil(), offre()).questions

        assert len(select_questions(questions, 99)) == len(questions)

    def test_synthese_sans_reponse_pas_de_moyenne(self) -> None:
        questions = build_preparation(profil(), offre()).questions[:3]

        resume = summarize(questions, {})

        assert resume.average_score is None
        assert resume.answered == 0
        assert resume.unanswered == tuple(q.id for q in questions)


class TestRelance:
    def test_date_proposee_deux_jours_apres_un_entretien_futur(self) -> None:
        data = InterviewData(scheduled_at=NOW + timedelta(days=3))

        assert suggest_follow_up_date(data, now=NOW) == NOW + timedelta(days=5)

    def test_date_proposee_depuis_maintenant_si_entretien_passe_ou_inconnu(self) -> None:
        assert suggest_follow_up_date(
            InterviewData(scheduled_at=NOW - timedelta(days=1)), now=NOW
        ) == NOW + timedelta(days=2)
        assert suggest_follow_up_date(InterviewData(), now=NOW) == NOW + timedelta(days=2)

    @pytest.mark.parametrize("langue,debut", [("fr", "Bonjour Marie,"), ("en", "Hello Marie,")])
    def test_brouillon_personnalise_sans_inventer(self, langue: str, debut: str) -> None:
        data = InterviewData(stage=InterviewStage.TECHNICAL, interviewers=("Marie",))

        brouillon = draft_follow_up(
            data, offre(), candidate_name="Camille Dubois", language=langue, now=NOW
        )

        assert brouillon.body.startswith(debut)
        assert "Ingénieur Backend" in brouillon.body
        assert "Acme" in brouillon.body
        assert "Camille Dubois" in brouillon.body
        assert "[" in brouillon.body  # point précis de l'échange à compléter par l'utilisateur


def test_offre_non_analysee_utilise_les_competences_du_profil_citees_dans_le_texte() -> None:
    contenu = build_preparation(
        profil(),
        offre(description="Stack : Python et Docker.", required_skills=()),
    )

    assert contenu.skills_matched == ("Python",)  # Docker n'est pas dans le profil : jamais ajouté
    assert any(q.skill == "Python" for q in contenu.questions)
    assert any("Offre non analysée" in w for w in contenu.warnings)
