"""Règles métier pures pour le calcul des récurrences, fuseaux et éligibilité."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.modules.notifications.domain.entities import NotificationPreferences
from app.modules.notifications.domain.enums import (
    NotificationKind,
    ScheduleFrequency,
)
from app.modules.notifications.domain.exceptions import (
    InvalidFrequencyError,
    InvalidTimezoneError,
)


def get_zone_info(tz_name: str) -> ZoneInfo:
    """Valide et retourne le fuseau horaire spécifié.

    Lève `InvalidTimezoneError` si le fuseau horaire est inconnu.
    """
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError) as err:
        raise InvalidTimezoneError(f"Fuseau horaire invalide : '{tz_name}'.") from err


def compute_next_run(
    frequency: ScheduleFrequency,
    *,
    from_time: datetime,
    tz_name: str = "Europe/Paris",
    target_hour: int | None = 8,
    target_minute: int | None = 0,
    interval_minutes: int | None = None,
) -> datetime:
    """Calcule la date/heure de la prochaine exécution en UTC.

    Gère précisément les fuseaux horaires et les changements d'heure via `ZoneInfo`.
    """
    tz = get_zone_info(tz_name)
    # Assure que from_time est localisé dans le fuseau horaire cible
    if from_time.tzinfo is None:
        local_time = from_time.replace(tzinfo=UTC).astimezone(tz)
    else:
        local_time = from_time.astimezone(tz)

    if frequency == ScheduleFrequency.HOURLY:
        prochain_local = local_time + timedelta(hours=1)
    elif frequency == ScheduleFrequency.EVERY_6_HOURS:
        prochain_local = local_time + timedelta(hours=6)
    elif frequency == ScheduleFrequency.INTERVAL_MINUTES:
        if interval_minutes is None or interval_minutes <= 0:
            raise InvalidFrequencyError(
                "L'intervalle en minutes doit être spécifié et strictement positif."
            )
        prochain_local = local_time + timedelta(minutes=interval_minutes)
    elif frequency == ScheduleFrequency.DAILY:
        h = 8 if target_hour is None else target_hour
        m = 0 if target_minute is None else target_minute
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise InvalidFrequencyError(
                f"Heure journalière invalide : {h:02d}:{m:02d} (doit être 00:00 - 23:59)."
            )
        candidat = local_time.replace(hour=h, minute=m, second=0, microsecond=0)
        if candidat <= local_time:
            candidat += timedelta(days=1)
        prochain_local = candidat
    else:
        raise InvalidFrequencyError(f"Fréquence inconnue : {frequency}")

    # Conversion systématique en UTC pour stockage et comparaisons normalisées
    return prochain_local.astimezone(UTC)


def should_notify(
    preferences: NotificationPreferences,
    kind: NotificationKind,
    *,
    match_score: int | None = None,
) -> bool:
    """Détermine si une notification doit être émise selon les préférences de l'utilisateur."""
    # Si le canal in-app et le canal email sont tous les deux coupés, aucune notification
    if not preferences.in_app_enabled and not preferences.email_enabled:
        return False

    if kind == NotificationKind.NEW_OFFERS:
        return preferences.notify_new_offers
    if kind == NotificationKind.RELEVANT_MATCH:
        if not preferences.notify_relevant_matches:
            return False
        return not (match_score is not None and match_score < preferences.min_relevance_score)
    if kind == NotificationKind.SEARCH_ERROR:
        return preferences.notify_search_errors
    if kind == NotificationKind.FOLLOW_UP_REMINDER:
        return preferences.notify_follow_up_reminders
    if kind == NotificationKind.AI_BUDGET_ALERT:
        return preferences.notify_ai_budget_alerts
    if kind == NotificationKind.DAILY_DIGEST:
        return preferences.daily_digest_enabled

    return True


def build_idempotency_key(
    task_type: str,
    target_id: str | None,
    time_bucket: str,
) -> str:
    """Génère une clé d'idempotence prévenant les exécutions concurrentes inutiles."""
    cible = target_id or "global"
    return f"{task_type}:{cible}:{time_bucket}"
