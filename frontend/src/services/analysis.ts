import type { AISummary, AnalysisResponse } from "@/types/analysis";

import { apiFetch } from "./api-client";

export const getAnalysis = (offerId: string) =>
  apiFetch<AnalysisResponse>(`/api/v1/offers/${encodeURIComponent(offerId)}/analysis`);

export const requestAISummary = (offerId: string) =>
  apiFetch<AISummary>(`/api/v1/offers/${encodeURIComponent(offerId)}/analysis/ai-summary`, {
    method: "POST",
  });
