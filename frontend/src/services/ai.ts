import type { AIMode, AISettings, AIUsage, BackendPreference } from "@/types/ai";

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
