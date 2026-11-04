"""Règles métier pour le suivi des candidatures (TASK-014-03, 17, 20, 22).

Respecte les contraintes absolues de Happly AI :
- Aucune candidature n'est envoyée automatiquement.
- Aucun chiffre n'est affiché sans donnée réelle sous-jacente.
- Machine à états stricte pour les statuts de candidature.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from app.modules.application_management.domain.enums import ApplicationStatus
from app.modules.application_management.domain.exceptions import (
    ExternalOfferLinkMissingError,
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


# Statuts de création : une candidature naît avant son envoi, jamais « envoyée » ou « répondue ».
INITIAL_STATUSES = frozenset(
    {
        ApplicationStatus.NEW_OFFER,
        ApplicationStatus.TO_ANALYZE,
        ApplicationStatus.TO_APPLY,
        ApplicationStatus.DOCUMENTS_TO_PREPARE,
    }
)

# Statuts depuis lesquels l'utilisateur peut confirmer qu'il a envoyé sa candidature.
SUBMITTABLE_STATUSES = frozenset(
    status for status, cibles in _ALLOWED_TRANSITIONS.items() if ApplicationStatus.SENT in cibles
)

RESPONSE_STATUSES = frozenset(
    {
        ApplicationStatus.INTERVIEW,
        ApplicationStatus.SECOND_INTERVIEW,
        ApplicationStatus.OFFER_RECEIVED,
        ApplicationStatus.REJECTED,
    }
)
FOLLOW_UP_STATUSES = frozenset({ApplicationStatus.SENT, ApplicationStatus.PENDING})


def allowed_status_targets(status: ApplicationStatus) -> list[ApplicationStatus]:
    """Statuts proposables depuis `status`, dans l'ordre du parcours.

    L'envoi est exclu : il ne se déduit pas d'un changement de statut mais d'une confirmation.
    """
    cibles = _ALLOWED_TRANSITIONS.get(status, set()) - {ApplicationStatus.SENT}
    return [s for s in ApplicationStatus if s in cibles]


def can_confirm_submission(app: ApplicationAggregate) -> bool:
    """Vrai si l'utilisateur peut encore déclarer avoir envoyé cette candidature."""
    return app.applied_at is None and app.status in SUBMITTABLE_STATUSES


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


def safe_external_url(url: str | None) -> str:
    """URL de candidature à ouvrir dans le navigateur de l'utilisateur (TASK-014-19).

    Refuse tout ce qui n'est pas un lien http(s) nu : schémas dangereux (`javascript:`),
    identifiants intégrés (hameçonnage), espaces ou caractères de contrôle.
    """
    nettoyee = (url or "").strip()
    if not nettoyee:
        raise ExternalOfferLinkMissingError(
            "Cette offre ne dispose pas d'URL externe de candidature."
        )
    if any(c.isspace() or ord(c) < 32 for c in nettoyee):
        raise ExternalOfferLinkMissingError("URL de candidature invalide.")
    morceaux = urlsplit(nettoyee)
    if (
        morceaux.scheme not in {"http", "https"}
        or not morceaux.hostname
        or morceaux.username
        or morceaux.password
    ):
        raise ExternalOfferLinkMissingError("URL de candidature invalide.")
    return nettoyee


def verify_dossier_readiness(dossier: ApplicationDossier) -> None:
    """Vérifie que les pièces requises sont présentes avant de marquer prête (TASK-014-17)."""
    if not dossier.is_ready_to_send:
        manquants = ", ".join(dossier.missing_elements)
        raise IncompleteDossierError(
            f"Le dossier de candidature est incomplet. Éléments manquants : {manquants}."
        )


def calculate_response_rate(sent_count: int, responses_count: int) -> float | None:
    """Taux de réponse réel (TASK-014-22), ou None sans candidature envoyée.

    Jamais de 0 % par défaut : zéro envoi ne donne aucun taux.
    """
    if sent_count <= 0:
        return None
    return round(min(responses_count, sent_count) / sent_count * 100.0, 1)


def missing_dossier_elements(
    *, has_cv: bool, has_letter: bool, application_url: str | None
) -> tuple[str, ...]:
    """Pièces manquantes du dossier (TASK-014-17)."""
    manquants: list[str] = []
    if not has_cv:
        manquants.append("CV personnalisé manquant")
    if not has_letter:
        manquants.append("Lettre de motivation manquante")
    if not application_url:
        manquants.append("Lien de candidature externe manquant")
    return tuple(manquants)


def compute_application_stats(
    applications: list[ApplicationAggregate], *, now: datetime
) -> ApplicationStats:
    """Statistiques consolidées sur une liste réelle (TASK-014-15, 22)."""
    from app.modules.application_management.domain.entities import ApplicationStats

    envoyees = [a for a in applications if a.is_sent]
    reponses = sum(1 for a in envoyees if a.has_response)
    actives = sum(
        1
        for a in applications
        if a.status not in {ApplicationStatus.REJECTED, ApplicationStatus.ABANDONED}
    )
    relances = [
        a for a in applications if a.follow_up_at is not None and a.status in FOLLOW_UP_STATUSES
    ]

    return ApplicationStats(
        total_applications=len(applications),
        sent_applications=len(envoyees),
        interviews_count=sum(
            1
            for a in applications
            if a.status in {ApplicationStatus.INTERVIEW, ApplicationStatus.SECOND_INTERVIEW}
        ),
        offers_received_count=sum(
            1 for a in applications if a.status == ApplicationStatus.OFFER_RECEIVED
        ),
        rejections_count=sum(1 for a in applications if a.status == ApplicationStatus.REJECTED),
        response_rate=calculate_response_rate(len(envoyees), reponses),
        active_applications=actives,
        responses_count=reponses,
        pending_follow_ups_count=len(relances),
        due_follow_ups_count=sum(
            1 for a in relances if a.follow_up_at is not None and a.follow_up_at <= now
        ),
    )
