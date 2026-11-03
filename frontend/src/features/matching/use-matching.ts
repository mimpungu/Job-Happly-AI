"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { offersKey } from "@/features/jobs/use-offers";
import {
  getOfferMatch,
  getWeights,
  recomputeScores,
  resetWeights,
  saveWeights,
} from "@/services/matching";

export const WEIGHTS_KEY = ["matching", "weights"] as const;

export function useOfferMatch(offerId: string) {
  return useQuery({
    queryKey: ["matching", "offer", offerId],
    queryFn: () => getOfferMatch(offerId),
    // Une absence de profil validé est un état normal, pas une panne à retenter.
    retry: false,
  });
}

export function useWeights() {
  return useQuery({ queryKey: WEIGHTS_KEY, queryFn: getWeights });
}

/** Changer les pondérations invalide les scores affichés : ils sont relus (ou recalculés) ensuite. */
function useWeightsWrite<V>(ecrire: (valeur: V) => ReturnType<typeof getWeights>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ecrire,
    onSuccess: (vue) => {
      client.setQueryData(WEIGHTS_KEY, vue);
      void client.invalidateQueries({ queryKey: ["matching", "offer"] });
      void client.invalidateQueries({ queryKey: offersKey });
    },
  });
}

export const useSaveWeights = () =>
  useWeightsWrite((poids: Record<string, number>) => saveWeights(poids));
export const useResetWeights = () => useWeightsWrite(() => resetWeights());

export function useRecompute() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: recomputeScores,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: offersKey });
      void client.invalidateQueries({ queryKey: ["matching", "offer"] });
    },
  });
}
