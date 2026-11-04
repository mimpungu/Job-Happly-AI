/** Contrats de l'API IA (docs/API.md). Les montants sont des chaînes décimales (précision exacte). */

export type AIMode = "disabled" | "economy" | "balanced" | "quality";
export type BackendPreference = "local_only" | "api_only" | "hybrid";

export interface AIProviderView {
  name: string;
  kind: "api" | "local";
  models: string[];
  /** Fin masquée de la clé d'API (jamais la clé) : permet de vérifier une rotation. */
  key_hint?: string | null;
  /** Palier gratuit : le fournisseur peut réutiliser et faire relire les contenus. */
  uses_data_for_training: boolean;
}

export interface AISettings {
  mode: AIMode;
  backend_preference: BackendPreference;
  per_operation_level1: string;
  per_operation_level2: string;
  currency: string;
  daily_budget: string | null;
  monthly_budget: string | null;
  alert_thresholds: number[];
  /** Plafond journalier par fournisseur payant (vide = seulement les plafonds globaux). */
  provider_daily_caps: Record<string, string>;
  /** Plafond journalier par type de tâche (vide = seulement les plafonds globaux). */
  task_daily_caps: Record<string, string>;
  /** Tâches IA de l'application, pour régler un plafond par tâche. */
  tasks: { task_type: string; label: string }[];
  budget_defined: boolean;
  api_consent: boolean;
  api_consent_at: string | null;
  providers: AIProviderView[];
  paid_calls_possible: boolean;
}

export interface AIUsageRow {
  at: string;
  provider: string;
  model: string;
  task_type: string;
  level: number;
  outcome: string;
  cache_hit: boolean;
  input_tokens: number;
  output_tokens: number;
  cost: string;
  currency: string;
}

export interface AIAlert {
  period: "daily" | "monthly";
  threshold: number;
  percent: string;
  spent: string;
  limit: string;
}

export interface AICostEstimate {
  provider: string;
  model: string;
  paid: boolean;
  cost: string;
  currency: string;
  allowed: boolean;
  reason: string | null;
}

export interface AIUsage {
  /** Plus haut seuil atteint par période, tant qu'il est franchi. */
  alerts: AIAlert[];
  currency: string;
  spent_today: string;
  spent_month: string;
  daily_budget: string | null;
  monthly_budget: string | null;
  percent_today: string | null;
  percent_month: string | null;
  by_provider_month: Record<string, string>;
  recent: AIUsageRow[];
}

export interface AITestResult {
  provider: string;
  model: string;
  cache_hit: boolean;
  cost: string;
  input_tokens: number;
  output_tokens: number;
  summary: string;
  skills: string[];
  crossed_thresholds: number[];
}
