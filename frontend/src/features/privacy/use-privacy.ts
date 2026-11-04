"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  eraseData,
  getAiTransfers,
  getHealth,
  getMetrics,
  getPrivacySettings,
  getPrivacySummary,
  getRetention,
  purgeExpired,
  setPersonalDataPolicy,
} from "@/services/privacy";

const root = ["privacy"] as const;

export const usePrivacySummary = () =>
  useQuery({ queryKey: [...root, "summary"], queryFn: getPrivacySummary });
export const useRetention = () =>
  useQuery({ queryKey: [...root, "retention"], queryFn: getRetention });
export const useAiTransfers = () =>
  useQuery({ queryKey: [...root, "ai"], queryFn: getAiTransfers });
export const usePrivacySettings = () =>
  useQuery({ queryKey: [...root, "settings"], queryFn: getPrivacySettings });
export const useHealth = () =>
  useQuery({ queryKey: ["health", "details"], queryFn: getHealth, refetchInterval: 30_000 });
export const useMetrics = () =>
  useQuery({ queryKey: ["health", "metrics"], queryFn: getMetrics, refetchInterval: 30_000 });

export function useSetPolicy() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: setPersonalDataPolicy,
    onSuccess: () => client.invalidateQueries({ queryKey: [...root, "settings"] }),
  });
}

/** Après une suppression, tout ce que l'application affiche peut avoir changé : on relit tout. */
export function useErase() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ scope, confirmation }: { scope: string; confirmation: string }) =>
      eraseData(scope, confirmation),
    onSuccess: () => client.invalidateQueries(),
  });
}

export function usePurge() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: purgeExpired,
    onSuccess: () => client.invalidateQueries({ queryKey: root }),
  });
}
