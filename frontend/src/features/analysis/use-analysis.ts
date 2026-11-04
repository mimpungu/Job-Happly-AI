"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getAnalysis, requestAISummary } from "@/services/analysis";

export const useOfferAnalysis = (offerId: string) =>
  useQuery({ queryKey: ["analysis", offerId], queryFn: () => getAnalysis(offerId) });

/** Le résumé passe par le journal IA : la consommation affichée doit être relue ensuite. */
export function useAISummary(offerId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => requestAISummary(offerId),
    onSettled: () => void client.invalidateQueries({ queryKey: ["ai", "usage"] }),
  });
}
