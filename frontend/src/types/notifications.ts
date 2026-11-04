/** Préférences de notification (docs/API.md, `/api/v1/notifications/preferences`). */

export interface NotificationPreferences {
  in_app_enabled: boolean;
  email_enabled: boolean;
  email_recipient: string | null;
  email_consent_given: boolean;
  notify_new_offers: boolean;
  notify_relevant_matches: boolean;
  min_relevance_score: number;
  notify_search_errors: boolean;
  notify_follow_up_reminders: boolean;
  notify_ai_budget_alerts: boolean;
  daily_digest_enabled: boolean;
  daily_digest_time: string;
  timezone: string;
}
