"""Adaptateur d'envoi d'e-mails sécurisé et conditionnel (ADR-0016)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.modules.notifications.domain.exceptions import (
    EmailConsentRequiredError,
    EmailNotConfiguredError,
)
from app.modules.notifications.domain.ports import EmailSenderPort

logger = logging.getLogger("happly.notifications.email")


@dataclass(frozen=True, slots=True)
class SentEmailRecord:
    recipient: str
    subject: str
    body: str
    sent_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class SafeEmailSender(EmailSenderPort):
    """Expéditeur d'e-mails appliquant les règles strictes de consentement et de sécurité.

    - Bloque tout envoi si `consent_verified` est faux (aucun e-mail sans consentement).
    - Par défaut en environnement local ou sans SMTP configuré : stocke les messages en mémoire pour
      l'audit et les tests sans effectuer de connexion réseau sortante non désirée.
    """

    def __init__(self, *, configured: bool = True) -> None:
        self._configured = configured
        self._outbox: list[SentEmailRecord] = []

    @property
    def outbox(self) -> tuple[SentEmailRecord, ...]:
        return tuple(self._outbox)

    def clear(self) -> None:
        self._outbox.clear()

    async def send_email(
        self,
        *,
        recipient: str,
        subject: str,
        body: str,
        consent_verified: bool,
    ) -> bool:
        if not consent_verified:
            logger.warning("Tentative d'envoi d'e-mail rejetée : consentement non accordé.")
            raise EmailConsentRequiredError(
                "L'envoi d'e-mail est bloqué : le consentement explicite n'a pas été accordé."
            )

        nettoye = recipient.strip()
        if not nettoye or "@" not in nettoye:
            raise EmailNotConfiguredError(f"Adresse destinataire invalide : '{recipient}'.")

        if not self._configured:
            raise EmailNotConfiguredError("Le service d'envoi d'e-mails n'est pas configuré.")

        enregistrement = SentEmailRecord(recipient=nettoye, subject=subject, body=body)
        self._outbox.append(enregistrement)
        logger.info(
            "Notification e-mail enregistrée (simulée/locale)",
            extra={"recipient": nettoye, "subject": subject},
        )
        return True
