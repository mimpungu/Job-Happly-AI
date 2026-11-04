"""Règles métier pour le suivi des candidatures (TASK-014-03, 17, 20, 22).

Respecte les contraintes absolues de Happly AI :
- Aucune candidature n'est envoyée automatiquement.
- Aucun chiffre n'est affiché sans donnée réelle sous-jacente.
- Machine à états stricte pour les statuts de candidature.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.modules.application_management.domain.enums import ApplicationStatus
from app.modules.application_management.domain.exceptions import (
    IncompleteDossierError,
    InvalidStatusTransitionError,
)

if TYPE_CHECKING:
    from app.modules.application_management.domain.entities import (
        ApplicationAggregate,
        ApplicationDossier,
        ApplicationStats,
    )

# Matrice des transitions d'états autorisées (spécification §12)
# Tout état peut transitionner vers ABANDONED.
_ALLOWED_TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
    ApplicationStatus.NEW_OFFER: {
        ApplicationStatus.TO_ANALYZE,
        ApplicationStatus.TO_APPLY,
        ApplicationStatus.DOCUMENTS_TO_PREPARE,
        ApplicationStatus.ABANDONED,
    },
    ApplicationStatus.TO_ANALYZE: {
        ApplicationStatus.TO_APPLY,
        ApplicationStatus.DOCUMENTS_TO_PREPARE,
        ApplicationStatus.ABANDONED,
    },
    ApplicationStatus.TO_APPLY: {
        ApplicationStatus.DOCUMENTS_TO_PREPARE,
        ApplicationStatus.READY_TO_SEND,
        ApplicationStatus.SENT,
        ApplicationStatus.ABANDONED,
    },
    ApplicationStatus.DOCUMENTS_TO_PREPARE: {
        ApplicationStatus.READY_TO_SEND,
        ApplicationStatus.SENT,
        ApplicationStatus.ABANDONED,
    },
    ApplicationStatus.READY_TO_SEND: {
        ApplicationStatus.SENT,
        ApplicationStatus.DOCUMENTS_TO_PREPARE,
        ApplicationStatus.ABANDONED,
    },
    ApplicationStatus.SENT: {
        ApplicationStatus.PENDING,
        ApplicationStatus.INTERVIEW,
        ApplicationStatus.OFFER_RECEIVED,
        ApplicationStatus.REJECTED,
        ApplicationStatus.ABANDONED,
    },
    ApplicationStatus.PENDING: {
        ApplicationStatus.INTERVIEW,
        ApplicationStatus.SECOND_INTERVIEW,
        ApplicationStatus.OFFER_RECEIVED,
        ApplicationStatus.REJECTED,
        ApplicationStatus.ABANDONED,
    },
    ApplicationStatus.INTERVIEW: {
        ApplicationStatus.SECOND_INTERVIEW,
        ApplicationStatus.OFFER_RECEIVED,
        ApplicationStatus.REJECTED,
        ApplicationStatus.ABANDONED,
    },
    ApplicationStatus.SECOND_INTERVIEW: {
        ApplicationStatus.OFFER_RECEIVED,
        ApplicationStatus.REJECTED,
        ApplicationStatus.ABANDONED,
    },
    ApplicationStatus.OFFER_RECEIVED: {
        ApplicationStatus.ABANDONED,
    },
    ApplicationStatus.REJECTED: {
        # Possibilité de relancer ou réactiver si le recruteur recontacte
        ApplicationStatus.INTERVIEW,
        ApplicationStatus.ABANDONED,
    },
    ApplicationStatus.ABANDONED: {
        # Possibilité de rouvrir une candidature abandonnée
        ApplicationStatus.NEW_OFFER,
        ApplicationStatus.TO_APPLY,
    },
}


def validate_status_transition(
    current_status: ApplicationStatus,
    target_status: ApplicationStatus,
) -> None:
    """Valide si une transition entre deux statuts est autorisée (TASK-014-03)."""
    if current_status == target_status:
        return

    allowed = _ALLOWED_TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        raise InvalidStatusTransitionError(
            f"Transition non autorisée du statut '{current_status.value}' "
            f"vers '{target_status.value}'."
        )


def verify_dossier_readiness(dossier: ApplicationDossier) -> None:
    """Vérifie que les pièces requises sont présentes avant de marquer prête (TASK-014-17)."""
    if not dossier.is_ready_to_send:
        manquants = ", ".join(dossier.missing_elements)
        raise IncompleteDossierError(
            f"Le dossier de candidature est incomplet. Éléments manquants : {manquants}."
        )


def calculate_response_rate(
    sent_count: int,
    responses_count: int,
) -> float:
    """Calcule le taux de réponse réel (TASK-014-22).

    Retourne 0.0 si aucune candidature n'a été envoyée (aucun faux chiffre).
    """
    if sent_count <= 0:
        return 0.0
    return round((responses_count / sent_count) * 100.0, 1)


def compute_application_stats(
    applications: list[ApplicationAggregate],
) -> ApplicationStats:
    """Calcule les statistiques consolidées sur une liste réelle (TASK-014-15, 22)."""
    total = len(applications)
    sent_apps = [app for app in applications if app.is_sent]
    sent_count = len(sent_apps)

    interviews_count = sum(
        1
        for app in applications
        if app.status in {ApplicationStatus.INTERVIEW, ApplicationStatus.SECOND_INTERVIEW}
    )
    offers_received_count = sum(
        1 for app in applications if app.status == ApplicationStatus.OFFER_RECEIVED
    )
    rejections_count = sum(1 for app in applications if app.status == ApplicationStatus.REJECTED)

    # Réponse reçue = toute candidature envoyée ayant reçu un retour (entretien, offre ou rejet)
    responses_count = sum(1 for app in sent_apps if app.has_response)
    rate = calculate_response_rate(sent_count, responses_count)

    active_count = sum(
        1
        for app in applications
        if app.status not in {ApplicationStatus.REJECTED, ApplicationStatus.ABANDONED}
    )

    pending_follow_ups = sum(
        1
        for app in applications
        if app.follow_up_at is not None
        and app.status in {ApplicationStatus.SENT, ApplicationStatus.PENDING}
    )

    from app.modules.application_management.domain.entities import ApplicationStats

    return ApplicationStats(
        total_applications=total,
        sent_applications=sent_count,
        interviews_count=interviews_count,
        offers_received_count=offers_received_count,
        rejections_count=rejections_count,
        response_rate=rate,
        active_applications=active_count,
        pending_follow_ups_count=pending_follow_ups,
    )
