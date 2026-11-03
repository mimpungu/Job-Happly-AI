/** Contrats de l'API IA (docs/API.md). Les montants sont des chaînes décimales (précision exacte). */

export type AIMode = "disabled" | "economy" | "balanced" | "quality";
export type BackendPreference = "local_only" | "api_only" | "hybrid";

export interface AIProviderView {
  name: string;
  kind: "api" | "local";
  models: string[];
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

export interface AIUsage {
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
