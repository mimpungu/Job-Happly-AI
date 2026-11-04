import type { MatchResponse, RecomputeReport, WeightsResponse } from "@/types/matching";

import { apiFetch } from "./api-client";

export const getOfferMatch = (offerId: string) =>
  apiFetch<MatchResponse>(`/api/v1/offers/${encodeURIComponent(offerId)}/match`);

export const recomputeScores = () =>
  apiFetch<RecomputeReport>("/api/v1/matching/recompute", { method: "POST" });

export const getWeights = () => apiFetch<WeightsResponse>("/api/v1/matching/weights");

export const saveWeights = (weights: Record<string, number>) =>
  apiFetch<WeightsResponse>("/api/v1/matching/weights", {
    method: "PUT",
    body: JSON.stringify({ weights }),
  });

export const resetWeights = () =>
  apiFetch<WeightsResponse>("/api/v1/matching/weights", { method: "DELETE" });
