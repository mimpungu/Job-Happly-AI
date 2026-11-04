"""Énumérations métier pour les notifications, la planification et l'orchestration."""

from __future__ import annotations

from enum import StrEnum


class NotificationKind(StrEnum):
    """Types de notifications gérés par Happly AI."""

    NEW_OFFERS = "new_offers"
    RELEVANT_MATCH = "relevant_match"
    SEARCH_ERROR = "search_error"
    FOLLOW_UP_REMINDER = "follow_up_reminder"
    AI_BUDGET_ALERT = "ai_budget_alert"
    DAILY_DIGEST = "daily_digest"


class ScheduleFrequency(StrEnum):
    """Fréquences de planification autorisées."""

    HOURLY = "hourly"
    EVERY_6_HOURS = "every_6_hours"
    DAILY = "daily"
    INTERVAL_MINUTES = "interval_minutes"


class ScheduledTaskType(StrEnum):
    """Types de tâches automatisables et planifiables."""

    RECURRING_SEARCH = "recurring_search"
    FOLLOW_UP_CHECK = "follow_up_check"
    AI_BUDGET_CHECK = "ai_budget_check"
    DAILY_DIGEST = "daily_digest"
    STALE_JOBS_CLEANUP = "stale_jobs_cleanup"

