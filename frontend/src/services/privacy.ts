import { env } from "@/lib/env";
import type {
  AITransfer,
  CategorySummary,
  ErasureResult,
  HealthReport,
  MetricsSnapshot,
  PersonalDataPolicy,
  PrivacySettings,
  RetentionRule,
} from "@/types/privacy";

import { apiFetch } from "./api-client";

const BASE = "/api/v1/privacy";

export const getPrivacySummary = () => apiFetch<CategorySummary[]>(`${BASE}/summary`);
export const getRetention = () => apiFetch<RetentionRule[]>(`${BASE}/retention`);
export const getAiTransfers = () => apiFetch<AITransfer[]>(`${BASE}/ai-transfers`);
export const getPrivacySettings = () => apiFetch<PrivacySettings>(`${BASE}/settings`);

export const setPersonalDataPolicy = (policy: PersonalDataPolicy) =>
  apiFetch<PrivacySettings>(`${BASE}/settings`, {
    method: "PUT",
    body: JSON.stringify({ personal_data_policy: policy }),
  });

/** Suppression définitive : le serveur exige le mot de confirmation, saisi par l'utilisateur. */
export const eraseData = (scope: string, confirmation: string) =>
  apiFetch<ErasureResult>(`${BASE}/erase`, {
    method: "POST",
    body: JSON.stringify({ scope, confirmation }),
  });

export const purgeExpired = () =>
  apiFetch<{ rows_purged: Record<string, number> }>(`${BASE}/retention/purge`, {
    method: "POST",
  });

/** Lien de téléchargement direct de l'archive : le navigateur gère l'enregistrement du fichier. */
export const EXPORT_URL = `${env.apiUrl}${BASE}/export`;

export const getHealth = () => apiFetch<HealthReport>("/api/v1/health/details");
export const getMetrics = () => apiFetch<MetricsSnapshot>("/api/v1/health/metrics");
