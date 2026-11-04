"""Service du CRM : création, statuts, envoi confirmé, relances, documents, dossier."""

import uuid
from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.modules.application_management.application.service import ApplicationTrackingService
from app.modules.application_management.domain.entities import ApplicationAggregate
from app.modules.application_management.domain.enums import ApplicationStatus as S
from app.modules.application_management.domain.enums import EventKind
from app.modules.application_management.domain.exceptions import (
    AlreadySubmittedError,
    ApplicationNotFoundError,
    DocumentKindMismatchError,
    DocumentLockedError,
    DocumentVersionNotFoundError,
    DuplicateApplicationError,
    ExternalOfferLinkMissingError,
    IncompleteDossierError,
    InvalidDateError,
    InvalidStatusTransitionError,
    NothingToAttachError,
    OfferNotFoundError,
)
from tests.unit.application_management.fakes import (
    MAINTENANT,
    OWNER,
    FakeDocuments,
    FakeOffers,
    InMemoryApplicationRepository,
)


class Contexte:
    def __init__(self) -> None:
        self.offers = FakeOffers()
        self.documents = FakeDocuments()
        self.repo = InMemoryApplicationRepository(self.offers)
        self.service = ApplicationTrackingService(
            self.repo, self.offers, self.documents, clock=lambda: MAINTENANT
        )

    async def candidature(self, statut: S = S.TO_APPLY, **offre: object) -> ApplicationAggregate:
        offre_id = self.offers.add(**offre)  # type: ignore[arg-type]
        return await self.service.create_application(
            owner_id=OWNER, offer_id=offre_id, initial_status=statut
        )

    async def prete(self) -> ApplicationAggregate:
        """Candidature au statut « prête à envoyer », dossier complet."""
        app = await self.candidature(S.DOCUMENTS_TO_PREPARE)
        cv = self.documents.add("cv", title="CV Python", version=2)
        lettre = self.documents.add("cover_letter", title="Lettre Acme")
        await self.service.attach_documents(
            owner_id=OWNER, application_id=app.id, cv_version_id=cv, letter_version_id=lettre
        )
        return await self.service.change_status(
            owner_id=OWNER, application_id=app.id, target_status=S.READY_TO_SEND
        )


@pytest.fixture
def ctx() -> Contexte:
    return Contexte()


# ---------------------------------------------------------------------------- création


async def test_creation_liee_a_l_offre_avec_premier_evenement(ctx: Contexte) -> None:
    app = await ctx.candidature(S.TO_APPLY)

    assert app.status is S.TO_APPLY
    assert app.offer is not None
    assert app.offer.title == "Développeur Python"
    assert [(e.kind, e.to_status) for e in app.events] == [(EventKind.STATUS_CHANGE, S.TO_APPLY)]


async def test_doublon_refuse(ctx: Contexte) -> None:
    app = await ctx.candidature()
    with pytest.raises(DuplicateApplicationError):
        await ctx.service.create_application(owner_id=OWNER, offer_id=app.offer_id)


async def test_offre_inconnue_refusee(ctx: Contexte) -> None:
    with pytest.raises(OfferNotFoundError):
        await ctx.service.create_application(owner_id=OWNER, offer_id=uuid.uuid4())


@pytest.mark.parametrize("statut", [S.SENT, S.PENDING, S.INTERVIEW, S.OFFER_RECEIVED, S.REJECTED])
async def test_creation_directement_envoyee_ou_repondue_refusee(ctx: Contexte, statut: S) -> None:
    """Avant : on pouvait créer une candidature « envoyée » sans aucune confirmation."""
    offre_id = ctx.offers.add()
    with pytest.raises(InvalidStatusTransitionError):
        await ctx.service.create_application(
            owner_id=OWNER, offer_id=offre_id, initial_status=statut
        )
    assert ctx.repo.apps == {}


async def test_une_candidature_ajoutee_par_erreur_peut_etre_supprimee_avec_son_historique(
    ctx: Contexte,
) -> None:
    app = await ctx.candidature()
    await ctx.service.add_note(owner_id=OWNER, application_id=app.id, note_body="Une note")

    await ctx.service.delete_application(owner_id=OWNER, application_id=app.id)

    with pytest.raises(ApplicationNotFoundError):
        await ctx.service.get_application(owner_id=OWNER, application_id=app.id)
    assert ctx.repo.events == [] and app.offer_id in ctx.offers.offers  # l'offre est conservée
    # L'offre peut être suivie à nouveau : la suppression a bien levé le doublon.
    again = await ctx.service.create_application(
        owner_id=OWNER, offer_id=app.offer_id, initial_status=S.TO_APPLY
    )
    assert again.id != app.id


async def test_supprimer_la_candidature_d_un_autre_utilisateur_est_refuse(
    ctx: Contexte,
) -> None:
    app = await ctx.candidature()

    with pytest.raises(ApplicationNotFoundError):
        await ctx.service.delete_application(owner_id=uuid.uuid4(), application_id=app.id)

    assert app.id in ctx.repo.apps


async def test_candidature_d_un_autre_utilisateur_introuvable(ctx: Contexte) -> None:
    app = await ctx.candidature()
    with pytest.raises(ApplicationNotFoundError):
        await ctx.service.get_application(owner_id=uuid.uuid4(), application_id=app.id)


# ---------------------------------------------------------------------------- statuts


async def test_changement_de_statut_historise_et_verrouille(ctx: Contexte) -> None:
    app = await ctx.candidature(S.NEW_OFFER)

    maj = await ctx.service.change_status(
        owner_id=OWNER, application_id=app.id, target_status=S.TO_ANALYZE, reason="  À creuser  "
    )

    assert maj.status is S.TO_ANALYZE
    dernier = maj.events[-1]
    assert (dernier.from_status, dernier.to_status, dernier.body) == (
        S.NEW_OFFER,
        S.TO_ANALYZE,
        "À creuser",
    )
    assert app.id in ctx.repo.locked  # deux changements simultanés ne s'écrasent pas


async def test_meme_statut_ne_cree_pas_d_evenement(ctx: Contexte) -> None:
    app = await ctx.candidature(S.TO_APPLY)
    avant = len(ctx.repo.events)

    await ctx.service.change_status(owner_id=OWNER, application_id=app.id, target_status=S.TO_APPLY)
    assert len(ctx.repo.events) == avant


async def test_transition_interdite(ctx: Contexte) -> None:
    app = await ctx.candidature(S.NEW_OFFER)
    with pytest.raises(InvalidStatusTransitionError):
        await ctx.service.change_status(
            owner_id=OWNER, application_id=app.id, target_status=S.OFFER_RECEIVED
        )


async def test_l_envoi_ne_se_deduit_pas_d_un_changement_de_statut(ctx: Contexte) -> None:
    """L'envoi passe par la confirmation explicite, avec sa date réelle."""
    app = await ctx.prete()
    with pytest.raises(InvalidStatusTransitionError, match="confirme explicitement"):
        await ctx.service.change_status(owner_id=OWNER, application_id=app.id, target_status=S.SENT)
    assert ctx.repo.apps[app.id].applied_at is None


async def test_prete_a_envoyer_exige_un_dossier_complet(ctx: Contexte) -> None:
    app = await ctx.candidature(S.DOCUMENTS_TO_PREPARE)
    with pytest.raises(IncompleteDossierError, match="CV personnalisé manquant"):
        await ctx.service.change_status(
            owner_id=OWNER, application_id=app.id, target_status=S.READY_TO_SEND
        )
    assert ctx.repo.apps[app.id].status is S.DOCUMENTS_TO_PREPARE


async def test_reponse_horodatee_une_seule_fois(ctx: Contexte) -> None:
    app = await ctx.prete()
    await ctx.service.confirm_manual_submission(owner_id=OWNER, application_id=app.id)

    entretien = await ctx.service.change_status(
        owner_id=OWNER, application_id=app.id, target_status=S.INTERVIEW
    )
    assert entretien.response_received_at == MAINTENANT

    ctx.repo.apps[app.id].response_received_at = MAINTENANT - timedelta(days=2)
    second = await ctx.service.change_status(
        owner_id=OWNER, application_id=app.id, target_status=S.SECOND_INTERVIEW
    )
    assert second.response_received_at == MAINTENANT - timedelta(days=2)  # date d'origine gardée


# ---------------------------------------------------------------------------- envoi confirmé


async def test_confirmation_d_envoi(ctx: Contexte) -> None:
    app = await ctx.prete()

    envoyee = await ctx.service.confirm_manual_submission(
        owner_id=OWNER, application_id=app.id, notes="Envoyée via le portail"
    )

    assert envoyee.status is S.SENT
    assert envoyee.applied_at == MAINTENANT
    dernier = envoyee.events[-1]
    assert (dernier.from_status, dernier.to_status) == (S.READY_TO_SEND, S.SENT)
    assert dernier.body is not None
    assert dernier.body.startswith("Envoyée via le portail")
    assert "2026-11-04 12:00 UTC" in dernier.body


async def test_confirmation_avec_la_vraie_date_d_envoi(ctx: Contexte) -> None:
    app = await ctx.candidature(S.TO_APPLY)
    veille = MAINTENANT - timedelta(days=1)

    envoyee = await ctx.service.confirm_manual_submission(
        owner_id=OWNER, application_id=app.id, applied_at=veille
    )
    assert envoyee.applied_at == veille


async def test_confirmation_avec_fuseau_non_utc_acceptee(ctx: Contexte) -> None:
    app = await ctx.candidature(S.TO_APPLY)
    paris = timezone(timedelta(hours=1))
    envoyee = await ctx.service.confirm_manual_submission(
        owner_id=OWNER,
        application_id=app.id,
        applied_at=datetime(2026, 11, 3, 9, 0, tzinfo=paris),
    )
    assert envoyee.applied_at == datetime(2026, 11, 3, 8, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    "date",
    [
        MAINTENANT + timedelta(days=1),  # dans le futur
        datetime(2026, 11, 3, 9, 0),
    ],
)
async def test_date_d_envoi_invalide(ctx: Contexte, date: datetime) -> None:
    app = await ctx.candidature(S.TO_APPLY)
    with pytest.raises(InvalidDateError):
        await ctx.service.confirm_manual_submission(
            owner_id=OWNER, application_id=app.id, applied_at=date
        )
    assert ctx.repo.apps[app.id].status is S.TO_APPLY


async def test_double_confirmation_refusee_et_date_d_origine_conservee(ctx: Contexte) -> None:
    """Avant : une seconde confirmation écrasait `applied_at`."""
    app = await ctx.candidature(S.TO_APPLY)
    premiere = MAINTENANT - timedelta(days=3)
    await ctx.service.confirm_manual_submission(
        owner_id=OWNER, application_id=app.id, applied_at=premiere
    )

    with pytest.raises(AlreadySubmittedError):
        await ctx.service.confirm_manual_submission(owner_id=OWNER, application_id=app.id)
    assert ctx.repo.apps[app.id].applied_at == premiere


@pytest.mark.parametrize("statut", [S.NEW_OFFER, S.TO_ANALYZE, S.ABANDONED, S.REJECTED])
async def test_confirmation_refusee_hors_preparation(ctx: Contexte, statut: S) -> None:
    app = await ctx.candidature(S.NEW_OFFER)
    ctx.repo.apps[app.id].status = statut
    with pytest.raises(InvalidStatusTransitionError):
        await ctx.service.confirm_manual_submission(owner_id=OWNER, application_id=app.id)


# ---------------------------------------------------------------------------- historique


async def test_note_et_entretien(ctx: Contexte) -> None:
    app = await ctx.candidature()
    entretien = datetime(2026, 11, 10, 14, 0, tzinfo=UTC)

    note = await ctx.service.add_note(
        owner_id=OWNER, application_id=app.id, note_body="  Bon contact  "
    )
    rdv = await ctx.service.add_interview_event(
        owner_id=OWNER, application_id=app.id, description="Entretien RH", interview_time=entretien
    )

    assert (note.kind, note.body) == (EventKind.NOTE, "Bon contact")
    assert (rdv.kind, rdv.occurred_at) == (EventKind.INTERVIEW, entretien)


async def test_entretien_sans_fuseau_refuse(ctx: Contexte) -> None:
    app = await ctx.candidature()
    with pytest.raises(InvalidDateError):
        await ctx.service.add_interview_event(
            owner_id=OWNER,
            application_id=app.id,
            description="x",
            interview_time=datetime(2026, 11, 10, 14, 0),
        )


async def test_contact_du_recruteur(ctx: Contexte) -> None:
    app = await ctx.candidature()
    contact = await ctx.service.add_contact(
        owner_id=OWNER,
        application_id=app.id,
        name="  Marc Lemoine ",
        email=" marc@acme.test ",
        phone="",
        role="Hiring Manager",
    )
    assert (contact.name, contact.email, contact.phone) == ("Marc Lemoine", "marc@acme.test", None)


# ---------------------------------------------------------------------------- relances


async def test_relance_planifiee_puis_annulee(ctx: Contexte) -> None:
    app = await ctx.prete()
    await ctx.service.confirm_manual_submission(owner_id=OWNER, application_id=app.id)
    dans_une_semaine = MAINTENANT + timedelta(days=7)

    planifiee = await ctx.service.schedule_follow_up(
        owner_id=OWNER, application_id=app.id, follow_up_at=dans_une_semaine, notes="Relancer RH"
    )
    assert planifiee.follow_up_at == dans_une_semaine
    assert planifiee.events[-1].kind is EventKind.FOLLOW_UP
    assert "2026-11-11 12:00 UTC" in (planifiee.events[-1].body or "")

    annulee = await ctx.service.schedule_follow_up(
        owner_id=OWNER, application_id=app.id, follow_up_at=None
    )
    assert annulee.follow_up_at is None
    assert annulee.events[-1].body == "Relance annulée."


async def test_on_ne_relance_pas_une_candidature_non_envoyee(ctx: Contexte) -> None:
    app = await ctx.candidature(S.TO_APPLY)
    with pytest.raises(InvalidDateError, match="déjà envoyée"):
        await ctx.service.schedule_follow_up(
            owner_id=OWNER, application_id=app.id, follow_up_at=MAINTENANT + timedelta(days=2)
        )


async def test_relance_dans_le_passe_ou_sans_fuseau_refusee(ctx: Contexte) -> None:
    app = await ctx.candidature(S.TO_APPLY)
    await ctx.service.confirm_manual_submission(owner_id=OWNER, application_id=app.id)

    with pytest.raises(InvalidDateError, match="futur"):
        await ctx.service.schedule_follow_up(
            owner_id=OWNER, application_id=app.id, follow_up_at=MAINTENANT - timedelta(days=1)
        )
    with pytest.raises(InvalidDateError, match="fuseau"):
        await ctx.service.schedule_follow_up(
            owner_id=OWNER,
            application_id=app.id,
            follow_up_at=datetime(2030, 1, 1),
        )


# ---------------------------------------------------------------------------- documents


async def test_association_de_versions_exactes_tracee(ctx: Contexte) -> None:
    app = await ctx.candidature()
    cv = ctx.documents.add("cv", title="CV Python", version=3)
    lettre = ctx.documents.add("cover_letter", title="Lettre Acme", version=1)

    maj = await ctx.service.attach_documents(
        owner_id=OWNER, application_id=app.id, cv_version_id=cv, letter_version_id=lettre
    )

    assert (maj.cv_version_id, maj.letter_version_id) == (cv, lettre)
    assert (
        maj.events[-1].body
        == "Documents associés : CV « CV Python » v3, Lettre « Lettre Acme » v1."
    )


async def test_association_exige_au_moins_une_version(ctx: Contexte) -> None:
    app = await ctx.candidature()
    with pytest.raises(NothingToAttachError):
        await ctx.service.attach_documents(owner_id=OWNER, application_id=app.id)


async def test_version_inconnue_ou_d_un_autre_utilisateur_refusee(ctx: Contexte) -> None:
    app = await ctx.candidature()
    with pytest.raises(DocumentVersionNotFoundError):
        await ctx.service.attach_documents(
            owner_id=OWNER, application_id=app.id, cv_version_id=uuid.uuid4()
        )
    assert ctx.repo.apps[app.id].cv_version_id is None


async def test_un_cv_n_est_pas_une_lettre(ctx: Contexte) -> None:
    app = await ctx.candidature()
    cv = ctx.documents.add("cv")
    lettre = ctx.documents.add("cover_letter")

    with pytest.raises(DocumentKindMismatchError):
        await ctx.service.attach_documents(
            owner_id=OWNER, application_id=app.id, letter_version_id=cv
        )
    with pytest.raises(DocumentKindMismatchError):
        await ctx.service.attach_documents(
            owner_id=OWNER, application_id=app.id, cv_version_id=lettre
        )


async def test_document_envoye_ne_peut_plus_etre_remplace(ctx: Contexte) -> None:
    """La version associée atteste de ce qui a réellement été envoyé."""
    app = await ctx.prete()
    await ctx.service.confirm_manual_submission(owner_id=OWNER, application_id=app.id)
    autre_cv = ctx.documents.add("cv", title="Autre CV")

    with pytest.raises(DocumentLockedError):
        await ctx.service.attach_documents(
            owner_id=OWNER, application_id=app.id, cv_version_id=autre_cv
        )


async def test_apres_envoi_on_peut_completer_un_emplacement_vide_ou_reassocier_le_meme(
    ctx: Contexte,
) -> None:
    app = await ctx.candidature(S.TO_APPLY)
    cv = ctx.documents.add("cv")
    await ctx.service.attach_documents(owner_id=OWNER, application_id=app.id, cv_version_id=cv)
    await ctx.service.confirm_manual_submission(owner_id=OWNER, application_id=app.id)

    lettre = ctx.documents.add("cover_letter")
    maj = await ctx.service.attach_documents(
        owner_id=OWNER, application_id=app.id, cv_version_id=cv, letter_version_id=lettre
    )
    assert maj.letter_version_id == lettre


async def test_description_des_documents_associes(ctx: Contexte) -> None:
    app = await ctx.prete()
    app = await ctx.service.get_application(owner_id=OWNER, application_id=app.id)
    from app.modules.application_management.domain.entities import AssociatedDocument

    app.documents = [
        AssociatedDocument(uuid.uuid4(), app.id, app.cv_version_id or uuid.uuid4(), MAINTENANT)
    ]
    infos = await ctx.service.describe_documents(app)
    assert [(i.kind, i.title, i.version) for i in infos] == [("cv", "CV Python", 2)]


# ---------------------------------------------------------------------------- dossier


async def test_dossier_incomplet_liste_ce_qui_manque(ctx: Contexte) -> None:
    app = await ctx.candidature()
    dossier = await ctx.service.prepare_dossier(owner_id=OWNER, application_id=app.id)

    assert dossier.is_ready_to_send is False
    assert dossier.missing_elements == (
        "CV personnalisé manquant",
        "Lettre de motivation manquante",
    )
    assert dossier.application_url == "https://careers.example.test/apply"
    assert dossier.job_title == "Développeur Python"


async def test_dossier_complet(ctx: Contexte) -> None:
    app = await ctx.prete()
    dossier = await ctx.service.prepare_dossier(owner_id=OWNER, application_id=app.id)

    assert dossier.is_ready_to_send is True
    assert dossier.missing_elements == ()
    assert dossier.warnings == ()


async def test_dossier_signale_un_audit_de_qualite_insuffisant(ctx: Contexte) -> None:
    app = await ctx.candidature(S.DOCUMENTS_TO_PREPARE)
    cv = ctx.documents.add("cv", passed=False, score=55)
    lettre = ctx.documents.add("cover_letter", passed=None)  # jamais audité : pas d'alerte
    await ctx.service.attach_documents(
        owner_id=OWNER, application_id=app.id, cv_version_id=cv, letter_version_id=lettre
    )

    dossier = await ctx.service.prepare_dossier(owner_id=OWNER, application_id=app.id)

    assert dossier.is_ready_to_send is True  # un avertissement ne bloque pas
    assert dossier.warnings == ("CV : l'audit de qualité n'est pas conforme (score 55/100).",)


# ---------------------------------------------------------------------------- lien externe


async def test_lien_externe_verifie(ctx: Contexte) -> None:
    app = await ctx.candidature(url="https://careers.example.test/jobs/1")
    url = await ctx.service.get_application_url_action(owner_id=OWNER, application_id=app.id)
    assert url == "https://careers.example.test/jobs/1"


@pytest.mark.parametrize("url", ["javascript:alert(1)", "https://u:p@example.test/", ""])
async def test_lien_externe_dangereux_refuse(ctx: Contexte, url: str) -> None:
    app = await ctx.candidature(url=url)
    with pytest.raises(ExternalOfferLinkMissingError):
        await ctx.service.get_application_url_action(owner_id=OWNER, application_id=app.id)


# ---------------------------------------------------------------------------- vues


async def test_statistiques_avec_horloge_injectee(ctx: Contexte) -> None:
    app = await ctx.candidature(S.TO_APPLY)
    await ctx.service.confirm_manual_submission(owner_id=OWNER, application_id=app.id)
    await ctx.candidature(S.NEW_OFFER)

    stats = await ctx.service.get_stats(owner_id=OWNER)

    assert (stats.total_applications, stats.sent_applications) == (2, 1)
    assert stats.response_rate == 0.0  # 1 envoi, 0 réponse : un vrai 0 %, pas une absence de donnée


async def test_kanban_total_reel_et_colonnes_limitees(ctx: Contexte) -> None:
    for _ in range(3):
        await ctx.candidature(S.TO_APPLY)

    colonnes = await ctx.service.get_kanban_view(owner_id=OWNER, per_column_limit=2)

    assert colonnes[S.TO_APPLY].count == 3
    assert len(colonnes[S.TO_APPLY].items) == 2
    assert set(colonnes) == set(S)
