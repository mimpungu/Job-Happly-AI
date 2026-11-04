"""Tests unitaires des règles métier pures du scheduler et des notifications."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from app.modules.notifications.domain.entities import NotificationPreferences
from app.modules.notifications.domain.enums import (
    NotificationKind,
    ScheduleFrequency,
)
from app.modules.notifications.domain.exceptions import (
    InvalidFrequencyError,
    InvalidTimezoneError,
)
from app.modules.notifications.domain.rules import (
    build_idempotency_key,
    compute_next_run,
    get_zone_info,
    should_notify,
)

T0_UTC = datetime(2026, 11, 4, 10, 0, 0, tzinfo=UTC)


class TestTimezonesAndRules:
    def test_valide_fuseaux_horaires_reconnus(self) -> None:
        tz_paris = get_zone_info("Europe/Paris")
        tz_utc = get_zone_info("UTC")
        assert tz_paris == ZoneInfo("Europe/Paris")
        assert tz_utc == ZoneInfo("UTC")

    def test_rejette_fuseau_invalide(self) -> None:
        with pytest.raises(InvalidTimezoneError):
            get_zone_info("Mars/Olympus_Mons")

    def test_calcul_prochain_run_hourly(self) -> None:
        next_run = compute_next_run(ScheduleFrequency.HOURLY, from_time=T0_UTC)
        assert next_run == datetime(2026, 11, 4, 11, 0, 0, tzinfo=UTC)

    def test_calcul_prochain_run_every_6_hours(self) -> None:
        next_run = compute_next_run(ScheduleFrequency.EVERY_6_HOURS, from_time=T0_UTC)
        assert next_run == datetime(2026, 11, 4, 16, 0, 0, tzinfo=UTC)

    def test_calcul_prochain_run_interval_minutes(self) -> None:
        next_run = compute_next_run(
            ScheduleFrequency.INTERVAL_MINUTES,
            from_time=T0_UTC,
            interval_minutes=45,
        )
        assert next_run == datetime(2026, 11, 4, 10, 45, 0, tzinfo=UTC)

    def test_interval_minutes_invalide_rejete(self) -> None:
        with pytest.raises(InvalidFrequencyError):
            compute_next_run(
                ScheduleFrequency.INTERVAL_MINUTES,
                from_time=T0_UTC,
                interval_minutes=0,
            )

    def test_calcul_prochain_run_daily_meme_jour_ou_lendemain(self) -> None:
        # A 10h UTC = 11h Paris (UTC+1 en novembre)
        # Si cible = 8h Paris -> déjà passée aujourd'hui -> programmée pour demain 8h Paris (7h UTC)
        next_run = compute_next_run(
            ScheduleFrequency.DAILY,
            from_time=T0_UTC,
            tz_name="Europe/Paris",
            target_hour=8,
            target_minute=0,
        )
        # Demain 8h00 Paris (UTC+1) = 7h00 UTC
        assert next_run == datetime(2026, 11, 5, 7, 0, 0, tzinfo=UTC)

        # Si cible = 14h Paris (13h UTC) -> aujourd'hui dans le futur
        next_run_futur = compute_next_run(
            ScheduleFrequency.DAILY,
            from_time=T0_UTC,
            tz_name="Europe/Paris",
            target_hour=14,
            target_minute=0,
        )
        assert next_run_futur == datetime(2026, 11, 4, 13, 0, 0, tzinfo=UTC)

    def test_heure_journaliere_invalide_rejetee(self) -> None:
        with pytest.raises(InvalidFrequencyError):
            compute_next_run(
                ScheduleFrequency.DAILY,
                from_time=T0_UTC,
                target_hour=25,
            )


class TestShouldNotify:
    @pytest.fixture
    def prefs(self) -> NotificationPreferences:
        return NotificationPreferences(
            id=uuid.uuid4(),
            owner_id=uuid.uuid4(),
            in_app_enabled=True,
            email_enabled=False,
            notify_new_offers=True,
            notify_relevant_matches=True,
            min_relevance_score=75,
            notify_search_errors=True,
            notify_follow_up_reminders=True,
            notify_ai_budget_alerts=True,
            daily_digest_enabled=True,
        )

    def test_autorise_si_preferences_actives(self, prefs: NotificationPreferences) -> None:
        assert should_notify(prefs, NotificationKind.NEW_OFFERS) is True
        assert should_notify(prefs, NotificationKind.SEARCH_ERROR) is True
        assert should_notify(prefs, NotificationKind.FOLLOW_UP_REMINDER) is True
        assert should_notify(prefs, NotificationKind.AI_BUDGET_ALERT) is True
        assert should_notify(prefs, NotificationKind.DAILY_DIGEST) is True

    def test_filtre_offres_pertinentes_selon_seuil(self, prefs: NotificationPreferences) -> None:
        # Seuil = 75
        assert should_notify(prefs, NotificationKind.RELEVANT_MATCH, match_score=80) is True
        assert should_notify(prefs, NotificationKind.RELEVANT_MATCH, match_score=75) is True
        assert should_notify(prefs, NotificationKind.RELEVANT_MATCH, match_score=70) is False

    def test_bloque_si_tous_canaux_desactives(self, prefs: NotificationPreferences) -> None:
        desactive = NotificationPreferences(
            id=prefs.id,
            owner_id=prefs.owner_id,
            in_app_enabled=False,
            email_enabled=False,
        )
        assert should_notify(desactive, NotificationKind.NEW_OFFERS) is False


class TestIdempotencyKey:
    def test_construction_cle_idempotence(self) -> None:
        cle = build_idempotency_key("recurring_search", "search-123", "2026110410")
        assert cle == "recurring_search:search-123:2026110410"

        cle_globale = build_idempotency_key("stale_jobs_cleanup", None, "20261104")
        assert cle_globale == "stale_jobs_cleanup:global:20261104"
