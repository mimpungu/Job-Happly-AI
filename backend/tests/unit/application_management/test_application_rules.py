"""Règles métier du CRM : statuts, dossier, statistiques réelles (TASK-014-03, 17, 22)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.application_management.domain.entities import (
    ApplicationAggregate,
    ApplicationDossier,
)
from app.modules.application_management.domain.enums import ApplicationStatus as S
from app.modules.application_management.domain.exceptions import (
    ExternalOfferLinkMissingError,
    IncompleteDossierError,
    InvalidStatusTransitionError,
)
from app.modules.application_management.domain.rules import (
    FOLLOW_UP_STATUSES,
    INITIAL_STATUSES,
    SUBMITTABLE_STATUSES,
    allowed_status_targets,
    calculate_response_rate,
    can_confirm_submission,
    compute_application_stats,
    missing_dossier_elements,
    safe_external_url,
    validate_status_transition,
    verify_dossier_readiness,
)

MAINTENANT = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


def _app(
    statut: S,
    *,
    applied: bool = False,
    response: bool = False,
    follow_up: datetime | None = None,
) -> ApplicationAggregate:
    return ApplicationAggregate(
        id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        offer_id=uuid.uuid4(),
        status=statut,
        created_at=MAINTENANT,
        updated_at=MAINTENANT,
        applied_at=MAINTENANT if applied else None,
        response_received_at=MAINTENANT if response else None,
        follow_up_at=follow_up,
    )


def test_transitions_de_statut_valides() -> None:
    validate_status_transition(S.NEW_OFFER, S.TO_APPLY)
    validate_status_transition(S.TO_APPLY, S.DOCUMENTS_TO_PREPARE)
    validate_status_transition(S.DOCUMENTS_TO_PREPARE, S.READY_TO_SEND)
    validate_status_transition(S.READY_TO_SEND, S.SENT)
    validate_status_transition(S.SENT, S.INTERVIEW)
    validate_status_transition(S.INTERVIEW, S.OFFER_RECEIVED)
    validate_status_transition(S.TO_APPLY, S.ABANDONED)
    validate_status_transition(S.SENT, S.SENT)  # même statut : idempotent


@pytest.mark.parametrize(
    ("depart", "cible"),
    [
        (S.NEW_OFFER, S.OFFER_RECEIVED),
        (S.NEW_OFFER, S.SENT),  # on n'envoie pas sans avoir préparé
        (S.OFFER_RECEIVED, S.TO_APPLY),
        (S.REJECTED, S.SENT),
        (S.ABANDONED, S.SENT),
    ],
)
def test_transition_de_statut_invalide(depart: S, cible: S) -> None:
    with pytest.raises(InvalidStatusTransitionError):
        validate_status_transition(depart, cible)


def test_une_candidature_naît_avant_son_envoi() -> None:
    assert S.SENT not in INITIAL_STATUSES
    assert S.INTERVIEW not in INITIAL_STATUSES
    assert S.OFFER_RECEIVED not in INITIAL_STATUSES
    assert S.NEW_OFFER in INITIAL_STATUSES


def test_seuls_les_statuts_de_preparation_permettent_de_confirmer_l_envoi() -> None:
    assert {S.TO_APPLY, S.DOCUMENTS_TO_PREPARE, S.READY_TO_SEND} == SUBMITTABLE_STATUSES


def test_statuts_proposables_excluent_l_envoi() -> None:
    assert S.SENT not in allowed_status_targets(S.READY_TO_SEND)
    assert allowed_status_targets(S.READY_TO_SEND) == [S.DOCUMENTS_TO_PREPARE, S.ABANDONED]
    assert allowed_status_targets(S.SENT) == [
        S.PENDING,
        S.INTERVIEW,
        S.OFFER_RECEIVED,
        S.REJECTED,
        S.ABANDONED,
    ]


def test_confirmation_possible_seulement_si_pas_deja_envoyee() -> None:
    assert can_confirm_submission(_app(S.READY_TO_SEND)) is True
    assert can_confirm_submission(_app(S.READY_TO_SEND, applied=True)) is False
    assert can_confirm_submission(_app(S.NEW_OFFER)) is False
    assert can_confirm_submission(_app(S.SENT, applied=True)) is False


@pytest.mark.parametrize(
    "url",
    [
        "https://careers.example.test/jobs/42?ref=happly",
        "http://example.test/apply",
        "  https://example.test/a  ",
    ],
)
def test_url_de_candidature_valide(url: str) -> None:
    assert safe_external_url(url) == url.strip()


@pytest.mark.parametrize(
    "url",
    [
        None,
        "",
        "   ",
        "javascript:alert(1)",
        "data:text/html,<script>1</script>",
        "ftp://example.test/file",
        "https://",
        "https://user:secret@example.test/apply",  # identifiants intégrés : hameçonnage
        "https://example.test/a b",
        "https://example.test/\nSet-Cookie: x=1",
        "//example.test/apply",
    ],
)
def test_url_de_candidature_refusee(url: str | None) -> None:
    with pytest.raises(ExternalOfferLinkMissingError):
        safe_external_url(url)


def test_pieces_manquantes_du_dossier() -> None:
    assert missing_dossier_elements(has_cv=True, has_letter=True, application_url="https://a") == ()
    assert missing_dossier_elements(has_cv=False, has_letter=False, application_url=None) == (
        "CV personnalisé manquant",
        "Lettre de motivation manquante",
        "Lien de candidature externe manquant",
    )


def test_verification_dossier_pret() -> None:
    verify_dossier_readiness(_dossier(()))


def _dossier(manquants: tuple[str, ...]) -> ApplicationDossier:
    return ApplicationDossier(
        application_id=uuid.uuid4(),
        offer_id=uuid.uuid4(),
        job_title="Développeur Python",
        company_name="Acme SAS",
        application_url="https://acme.test/apply",
        has_cv=not manquants,
        cv_version_id=None,
        has_letter=True,
        letter_version_id=uuid.uuid4(),
        is_ready_to_send=not manquants,
        missing_elements=manquants,
    )


def test_verification_dossier_incomplet_leve_exception() -> None:
    with pytest.raises(IncompleteDossierError, match="CV manquant"):
        verify_dossier_readiness(_dossier(("CV manquant", "Lien externe manquant")))


def test_taux_de_reponse_sans_envoi_n_existe_pas() -> None:
    """Avant : 0.0 s'affichait comme « 0 % de réponses » alors qu'il n'y a aucune donnée."""
    assert calculate_response_rate(sent_count=0, responses_count=0) is None
    assert calculate_response_rate(sent_count=0, responses_count=5) is None


def test_taux_de_reponse_sur_donnees_reelles() -> None:
    assert calculate_response_rate(sent_count=4, responses_count=2) == 50.0
    assert calculate_response_rate(sent_count=3, responses_count=1) == 33.3


def test_taux_de_reponse_ne_depasse_jamais_100() -> None:
    assert calculate_response_rate(sent_count=2, responses_count=5) == 100.0


def test_statistiques_vides_sans_taux() -> None:
    stats = compute_application_stats([], now=MAINTENANT)
    assert stats.total_applications == 0
    assert stats.response_rate is None


def test_consolidation_statistiques_reelles() -> None:
    avenir = MAINTENANT + timedelta(days=3)
    passe = MAINTENANT - timedelta(days=1)
    applications = [
        _app(S.SENT, applied=True, follow_up=passe),
        _app(S.PENDING, applied=True, follow_up=avenir),
        _app(S.INTERVIEW, applied=True, response=True),
        _app(S.REJECTED, applied=True, response=True),
        _app(S.ABANDONED, applied=True),  # envoyée puis abandonnée : compte comme envoyée
        _app(S.NEW_OFFER),
    ]

    stats = compute_application_stats(applications, now=MAINTENANT)

    assert stats.total_applications == 6
    assert stats.sent_applications == 5
    assert stats.interviews_count == 1
    assert stats.rejections_count == 1
    assert stats.response_rate == 40.0  # 2 réponses sur 5 envois
    assert stats.active_applications == 4  # ni rejetée ni abandonnée
    assert stats.pending_follow_ups_count == 2
    assert stats.due_follow_ups_count == 1  # seule la relance déjà échue


def test_relance_planifiee_sur_candidature_non_envoyee_n_est_pas_comptee() -> None:
    stats = compute_application_stats(
        [_app(S.TO_APPLY, follow_up=MAINTENANT - timedelta(days=1))], now=MAINTENANT
    )
    assert stats.pending_follow_ups_count == 0
    assert stats.due_follow_ups_count == 0
    assert S.SENT in FOLLOW_UP_STATUSES
