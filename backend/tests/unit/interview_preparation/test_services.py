"""Services de préparation, simulation et fiches entretien, sur doublures en mémoire."""

import uuid
from datetime import datetime, timedelta

import pytest

from app.modules.interview_preparation.application.interview_service import InterviewService
from app.modules.interview_preparation.application.preparation_service import PreparationService
from app.modules.interview_preparation.application.simulation_service import SimulationService
from app.modules.interview_preparation.domain.enums import (
    AssistMode,
    InterviewOutcome,
    InterviewStage,
    QuestionCategory,
    QuestionSource,
    SimulationStatus,
)
from app.modules.interview_preparation.domain.exceptions import (
    InterviewNotFoundError,
    InvalidInterviewDateError,
    PreparationNotFoundError,
    PreparationRequiredError,
    SimulationClosedError,
    SimulationNotFoundError,
    UnknownQuestionError,
)
from app.modules.interview_preparation.domain.models import InterviewData, Question
from tests.unit.interview_preparation.support import (
    APPLICATION,
    NOW,
    OWNER,
    FakeCoach,
    FakeRepository,
    FakeSources,
    FakeTracker,
)


def _question_ia(texte: str) -> Question:
    return Question(
        id="x",
        category=QuestionCategory.TECHNICAL,
        text=texte,
        rationale="Spécifique au poste.",
        source=QuestionSource.AI,
    )


def _preparation(coach: FakeCoach | None = None, cv: uuid.UUID | None = None):  # type: ignore[no-untyped-def]
    depot = FakeRepository()
    return PreparationService(FakeSources(cv), depot, coach), depot


class TestPreparationService:
    async def test_sans_ia_par_defaut_et_sans_appel(self) -> None:
        coach = FakeCoach([_question_ia("Comment testez-vous vos API ?")])
        service, _ = _preparation(coach, cv=uuid.uuid4())

        rec = await service.generate(owner_id=OWNER, application_id=APPLICATION)

        assert coach.calls == []
        assert rec.meta["ai"] == {"requested": "none", "status": "not_requested"}
        assert all(q.source is QuestionSource.RULES for q in rec.content.questions)
        assert rec.meta["cv_version_id"] is not None

    async def test_cv_non_associe_est_signale(self) -> None:
        service, _ = _preparation()

        rec = await service.generate(owner_id=OWNER, application_id=APPLICATION)

        assert any("Aucun CV" in w for w in rec.content.warnings)

    async def test_questions_ia_ajoutees_dedupliquees_et_plafonnees(self) -> None:
        deja = "Pourquoi quittez-vous (ou avez-vous quitté) votre poste actuel ?"
        propositions = [_question_ia(f"Question spécifique numéro {i} ?") for i in range(8)]
        coach = FakeCoach([_question_ia(deja), *propositions])
        service, _ = _preparation(coach)

        rec = await service.generate(owner_id=OWNER, application_id=APPLICATION, mode=AssistMode.AI)

        ajoutees = [q for q in rec.content.questions if q.source is QuestionSource.AI]
        assert len(ajoutees) == 5
        assert [q.id for q in ajoutees] == [f"ai-{i}" for i in range(1, 6)]
        assert rec.meta["ai"] == {"requested": "ai", "status": "applied", "added": 5}
        assert coach.calls == [AssistMode.AI]

    async def test_ia_indisponible_garde_la_base_et_le_dit(self) -> None:
        service, _ = _preparation(FakeCoach(fail=True))

        rec = await service.generate(
            owner_id=OWNER, application_id=APPLICATION, mode=AssistMode.LOCAL
        )

        assert rec.meta["ai"]["status"] == "unavailable"
        assert rec.meta["ai"]["reason"] == "Plafond atteint."
        assert rec.content.questions  # la préparation de base est livrée

    async def test_sans_adaptateur_ia_refus_explicite(self) -> None:
        service, _ = _preparation(None)

        rec = await service.generate(owner_id=OWNER, application_id=APPLICATION, mode=AssistMode.AI)

        assert rec.meta["ai"]["status"] == "unavailable"

    async def test_get_sans_preparation(self) -> None:
        service, _ = _preparation()

        with pytest.raises(PreparationNotFoundError):
            await service.get(owner_id=OWNER, application_id=APPLICATION)


async def _simulation_prete(coach: FakeCoach | None = None):  # type: ignore[no-untyped-def]
    depot = FakeRepository()
    sources = FakeSources()
    await PreparationService(sources, depot).generate(owner_id=OWNER, application_id=APPLICATION)
    service = SimulationService(sources, depot, depot, coach, clock=lambda: NOW)
    return service, depot


REPONSE = (
    "Dans mon poste chez OpenCorp, j'ai migré 12 services vers FastAPI. "
    "Ce qui a permis de réduire la dette technique de l'équipe. " + "Nous avons itéré. " * 6
)


class TestSimulationService:
    async def test_demarrage_exige_une_preparation(self) -> None:
        depot = FakeRepository()
        service = SimulationService(FakeSources(), depot, depot)

        with pytest.raises(PreparationRequiredError):
            await service.start(owner_id=OWNER, application_id=APPLICATION)

    async def test_demarrage_sans_appel_ia_et_questions_copiees(self) -> None:
        coach = FakeCoach()
        service, _ = await _simulation_prete(coach)

        sim = await service.start(owner_id=OWNER, application_id=APPLICATION, question_count=4)

        assert len(sim.questions) == 4
        assert sim.status is SimulationStatus.IN_PROGRESS
        assert coach.calls == []

    async def test_reponse_evaluee_remplacable_et_synthese(self) -> None:
        service, _ = await _simulation_prete()
        sim = await service.start(owner_id=OWNER, application_id=APPLICATION, question_count=3)
        q1, q2, _ = sim.questions

        faible = await service.answer(
            owner_id=OWNER, simulation_id=sim.id, question_id=q1.id, text="Je sais pas."
        )
        mieux = await service.answer(
            owner_id=OWNER, simulation_id=sim.id, question_id=q1.id, text=REPONSE
        )
        await service.answer(owner_id=OWNER, simulation_id=sim.id, question_id=q2.id, text=REPONSE)
        _, resume = await service.get(owner_id=OWNER, simulation_id=sim.id)

        assert mieux.feedback.score > faible.feedback.score
        assert resume.answered == 2 and resume.total == 3
        assert resume.average_score is not None
        assert len(resume.unanswered) == 1

    async def test_chiffre_du_parcours_connu_chiffre_invente_signale(self) -> None:
        service, _ = await _simulation_prete()
        sim = await service.start(owner_id=OWNER, application_id=APPLICATION, question_count=1)
        qid = sim.questions[0].id

        connu = await service.answer(
            owner_id=OWNER, simulation_id=sim.id, question_id=qid, text=REPONSE
        )
        invente = await service.answer(
            owner_id=OWNER, simulation_id=sim.id, question_id=qid, text=REPONSE.replace("12", "900")
        )

        assert connu.feedback.unverified_numbers == ()
        assert invente.feedback.unverified_numbers == ("900",)

    async def test_question_inconnue(self) -> None:
        service, _ = await _simulation_prete()
        sim = await service.start(owner_id=OWNER, application_id=APPLICATION)

        with pytest.raises(UnknownQuestionError):
            await service.answer(
                owner_id=OWNER, simulation_id=sim.id, question_id="nope", text="Bonjour"
            )

    async def test_simulation_terminee_en_lecture_seule_et_completion_idempotente(self) -> None:
        service, _ = await _simulation_prete()
        sim = await service.start(owner_id=OWNER, application_id=APPLICATION, question_count=2)
        await service.answer(
            owner_id=OWNER, simulation_id=sim.id, question_id=sim.questions[0].id, text=REPONSE
        )

        premiere, _ = await service.complete(owner_id=OWNER, simulation_id=sim.id)
        seconde, _ = await service.complete(owner_id=OWNER, simulation_id=sim.id)

        assert premiere.status is SimulationStatus.COMPLETED
        assert seconde.completed_at == premiere.completed_at
        with pytest.raises(SimulationClosedError):
            await service.answer(
                owner_id=OWNER, simulation_id=sim.id, question_id=sim.questions[1].id, text="Ok"
            )

    async def test_commentaire_ia_a_la_demande_uniquement(self) -> None:
        coach = FakeCoach(comments=("Précisez le résultat.",))
        service, _ = await _simulation_prete(coach)
        sim = await service.start(owner_id=OWNER, application_id=APPLICATION, question_count=1)
        qid = sim.questions[0].id

        sans = await service.answer(
            owner_id=OWNER, simulation_id=sim.id, question_id=qid, text=REPONSE
        )
        avec = await service.answer(
            owner_id=OWNER, simulation_id=sim.id, question_id=qid, text=REPONSE, mode=AssistMode.AI
        )

        assert sans.feedback.ai_status is None and sans.feedback.ai_comments == ()
        assert avec.feedback.ai_status == "applied"
        assert avec.feedback.ai_comments == ("Précisez le résultat.",)
        assert coach.calls == [AssistMode.AI]

    async def test_ia_en_panne_le_retour_de_base_est_conserve(self) -> None:
        service, _ = await _simulation_prete(FakeCoach(fail=True))
        sim = await service.start(owner_id=OWNER, application_id=APPLICATION, question_count=1)

        rep = await service.answer(
            owner_id=OWNER,
            simulation_id=sim.id,
            question_id=sim.questions[0].id,
            text=REPONSE,
            mode=AssistMode.LOCAL,
        )

        assert rep.feedback.ai_status == "unavailable"
        assert rep.feedback.score > 0

    async def test_historique_et_suppression(self) -> None:
        service, _ = await _simulation_prete()
        a = await service.start(owner_id=OWNER, application_id=APPLICATION)
        await service.start(owner_id=OWNER, application_id=APPLICATION)

        assert len(await service.list(owner_id=OWNER, application_id=APPLICATION)) == 2
        await service.delete(owner_id=OWNER, simulation_id=a.id)
        assert len(await service.list(owner_id=OWNER, application_id=APPLICATION)) == 1
        with pytest.raises(SimulationNotFoundError):
            await service.delete(owner_id=OWNER, simulation_id=a.id)


def _entretiens(now: datetime = NOW):  # type: ignore[no-untyped-def]
    depot, suivi = FakeRepository(), FakeTracker()
    return InterviewService(FakeSources(), depot, suivi, clock=lambda: now), suivi


class TestInterviewService:
    async def test_creation_datee_alimente_l_historique_de_la_candidature(self) -> None:
        service, suivi = _entretiens()
        quand = NOW + timedelta(days=2)

        fiche = await service.create(
            owner_id=OWNER,
            application_id=APPLICATION,
            data=InterviewData(
                stage=InterviewStage.TECHNICAL, scheduled_at=quand, location="Visio"
            ),
        )

        assert fiche.data.scheduled_at == quand
        assert suivi.events == [("Entretien technique planifié (Visio)", quand)]

    async def test_creation_sans_date_n_ecrit_rien_dans_le_suivi(self) -> None:
        service, suivi = _entretiens()

        await service.create(owner_id=OWNER, application_id=APPLICATION, data=InterviewData())

        assert suivi.events == []

    async def test_date_sans_fuseau_refusee(self) -> None:
        service, _ = _entretiens()

        with pytest.raises(InvalidInterviewDateError):
            await service.create(
                owner_id=OWNER,
                application_id=APPLICATION,
                data=InterviewData(scheduled_at=datetime(2026, 11, 10, 9, 0)),
            )

    async def test_report_et_issue_sont_traces(self) -> None:
        service, suivi = _entretiens()
        t1, t2 = NOW + timedelta(days=2), NOW + timedelta(days=4)
        fiche = await service.create(
            owner_id=OWNER,
            application_id=APPLICATION,
            data=InterviewData(stage=InterviewStage.MANAGER, scheduled_at=t1),
        )

        await service.update(
            owner_id=OWNER,
            interview_id=fiche.id,
            data=InterviewData(stage=InterviewStage.MANAGER, scheduled_at=t2),
        )
        maj = await service.update(
            owner_id=OWNER,
            interview_id=fiche.id,
            data=InterviewData(
                stage=InterviewStage.MANAGER,
                scheduled_at=t2,
                outcome=InterviewOutcome.POSITIVE,
                feedback_notes="Bon échange.",
            ),
        )

        assert [e[0] for e in suivi.events] == [
            "Entretien manager planifié",
            "Entretien manager reprogrammé",
            "Entretien manager terminé : issue « positive »",
        ]
        assert maj.data.feedback_notes == "Bon échange."

    async def test_fiche_introuvable(self) -> None:
        service, _ = _entretiens()

        with pytest.raises(InterviewNotFoundError):
            await service.get(owner_id=OWNER, interview_id=uuid.uuid4())

    async def test_brouillon_puis_relance_planifiee_a_la_date_proposee(self) -> None:
        service, suivi = _entretiens()
        passe = NOW - timedelta(days=1)
        fiche = await service.create(
            owner_id=OWNER,
            application_id=APPLICATION,
            data=InterviewData(scheduled_at=passe, interviewers=("Marie",)),
        )

        avec_brouillon = await service.draft_follow_up(owner_id=OWNER, interview_id=fiche.id)
        quand = await service.schedule_follow_up(
            owner_id=OWNER, interview_id=fiche.id, follow_up_at=None
        )

        assert avec_brouillon.follow_up_draft is not None
        assert "Bonjour Marie," in avec_brouillon.follow_up_draft.body
        assert "Camille Dubois" in avec_brouillon.follow_up_draft.body
        assert quand == NOW + timedelta(days=2) == suivi.follow_ups[0]

    async def test_la_mise_a_jour_conserve_le_brouillon(self) -> None:
        service, _ = _entretiens()
        fiche = await service.create(
            owner_id=OWNER, application_id=APPLICATION, data=InterviewData()
        )
        await service.draft_follow_up(owner_id=OWNER, interview_id=fiche.id)

        maj = await service.update(
            owner_id=OWNER, interview_id=fiche.id, data=InterviewData(notes="Préparé.")
        )

        assert maj.follow_up_draft is not None

    async def test_relance_date_sans_fuseau_refusee(self) -> None:
        service, _ = _entretiens()
        fiche = await service.create(
            owner_id=OWNER, application_id=APPLICATION, data=InterviewData()
        )

        with pytest.raises(InvalidInterviewDateError):
            await service.schedule_follow_up(
                owner_id=OWNER, interview_id=fiche.id, follow_up_at=datetime(2026, 11, 20, 9, 0)
            )

    async def test_liste_a_venir(self) -> None:
        service, _ = _entretiens()
        await service.create(
            owner_id=OWNER,
            application_id=APPLICATION,
            data=InterviewData(scheduled_at=NOW - timedelta(days=3)),
        )
        futur = await service.create(
            owner_id=OWNER,
            application_id=APPLICATION,
            data=InterviewData(scheduled_at=NOW + timedelta(days=3)),
        )

        a_venir = await service.list(owner_id=OWNER, upcoming_only=True)

        assert [i.id for i in a_venir] == [futur.id]
        assert len(await service.list(owner_id=OWNER, application_id=APPLICATION)) == 2
