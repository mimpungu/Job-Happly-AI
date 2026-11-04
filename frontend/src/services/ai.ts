import type {
  AICostEstimate,
  AIMode,
  AISettings,
  AITestResult,
  AIUsage,
  BackendPreference,
} from "@/types/ai";

import { apiFetch } from "./api-client";

export const getAISettings = () => apiFetch<AISettings>("/api/v1/ai/settings");

export const saveAISettings = (corps: { mode?: AIMode; backend_preference?: BackendPreference }) =>
  apiFetch<AISettings>("/api/v1/ai/settings", { method: "PUT", body: JSON.stringify(corps) });

export const saveAIBudget = (corps: { daily: string; monthly: string; currency: string }) =>
  apiFetch<AISettings>("/api/v1/ai/budget", { method: "PUT", body: JSON.stringify(corps) });

export const saveAIConsent = (accepted: boolean) =>
  apiFetch<AISettings>("/api/v1/ai/consent", {
    method: "PUT",
    body: JSON.stringify({ accepted }),
  });

export const getAIUsage = () => apiFetch<AIUsage>("/api/v1/ai/usage");

export const runAITest = (level: 1 | 2) =>
  apiFetch<AITestResult>("/api/v1/ai/test", { method: "POST", body: JSON.stringify({ level }) });

export const saveProviderCap = (provider: string, daily: string | null) =>
  apiFetch<AISettings>(`/api/v1/ai/provider-caps/${encodeURIComponent(provider)}`, {
    method: "PUT",
    body: JSON.stringify({ daily }),
  });

/** Coût maximal d'une opération, calculé sans appeler de modèle. */
export const estimateAICost = (
  corps: { characters: number; level: 1 | 2 } | { task_type: string },
) =>
  apiFetch<AICostEstimate>("/api/v1/ai/estimate", { method: "POST", body: JSON.stringify(corps) });

export const saveTaskCap = (taskType: string, daily: string | null) =>
  apiFetch<AISettings>(`/api/v1/ai/task-caps/${encodeURIComponent(taskType)}`, {
    method: "PUT",
    body: JSON.stringify({ daily }),
  });
