/** Contrats de l'API de confidentialité et de santé (EPIC 018). */

export type DataCategory =
  | "profile"
  | "documents"
  | "applications"
  | "interviews"
  | "offers"
  | "ai_activity"
  | "notifications"
  | "settings";

export interface CategorySummary {
  category: DataCategory;
  label: string;
  rows: number;
  file_bytes: number;
  tables: Record<string, number>;
}

export interface ErasureResult {
  scope: string;
  total_rows: number;
  rows_deleted: Record<string, number>;
  files_deleted: number;
  files_failed: number;
  notes: string[];
}

export interface RetentionRule {
  table: string;
  category: DataCategory;
  /** `null` : conservé jusqu'à suppression par l'utilisateur. */
  days: number | null;
  description: string;
  automatic: boolean;
}

export interface AITransfer {
  task_type: string;
  purpose: string;
  data_sent: string;
  never_sent: string;
  personal_data: boolean;
  optional: boolean;
}

export type PersonalDataPolicy = "allowed" | "local_only" | "never";

export interface PrivacySettings {
  personal_data_policy: PersonalDataPolicy;
  confirmation_word: string;
}

export type HealthStatus = "ok" | "degraded" | "down" | "not_configured";

export interface ComponentHealth {
  name: string;
  status: HealthStatus;
  detail: string | null;
  data: Record<string, unknown>;
}

export interface HealthReport {
  status: HealthStatus;
  components: ComponentHealth[];
}

export interface RouteMetrics {
  count: number;
  errors: number;
  avg_ms: number;
  p50_ms: number;
  p95_ms: number;
}

export interface MetricsSnapshot {
  uptime_seconds: number;
  requests: number;
  server_errors: number;
  rate_limited: number;
  routes: Record<string, RouteMetrics>;
}
