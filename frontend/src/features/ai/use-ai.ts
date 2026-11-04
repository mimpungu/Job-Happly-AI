"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getAISettings,
  getAIUsage,
  runAITest,
  saveAIBudget,
  saveAIConsent,
  saveAISettings,
} from "@/services/ai";

export const AI_SETTINGS_KEY = ["ai", "settings"] as const;
export const AI_USAGE_KEY = ["ai", "usage"] as const;

export const useAISettings = () => useQuery({ queryKey: AI_SETTINGS_KEY, queryFn: getAISettings });
export const useAIUsage = () => useQuery({ queryKey: AI_USAGE_KEY, queryFn: getAIUsage });

/** Toute modification de réglage renvoie l'état complet : le cache est remplacé, pas relu. */
function useSettingsWrite<V>(ecrire: (valeur: V) => ReturnType<typeof getAISettings>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ecrire,
    onSuccess: (vue) => {
      client.setQueryData(AI_SETTINGS_KEY, vue);
      void client.invalidateQueries({ queryKey: AI_USAGE_KEY });
    },
  });
}

export const useSaveAISettings = () => useSettingsWrite(saveAISettings);
export const useSaveAIBudget = () => useSettingsWrite(saveAIBudget);
export const useSaveAIConsent = () => useSettingsWrite(saveAIConsent);

/** Un test passe par le journal : la consommation affichée doit être relue ensuite. */
export function useAITest() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: runAITest,
    onSettled: () => void client.invalidateQueries({ queryKey: AI_USAGE_KEY }),
  });
}
