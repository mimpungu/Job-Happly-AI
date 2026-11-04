"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  estimateAICost,
  getAISettings,
  getAIUsage,
  runAITest,
  saveAIBudget,
  saveAIConsent,
  saveAISettings,
  saveProviderCap,
  saveTaskCap,
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
export const useSaveProviderCap = () =>
  useSettingsWrite(({ provider, daily }: { provider: string; daily: string | null }) =>
    saveProviderCap(provider, daily),
  );

export const useSaveTaskCap = () =>
  useSettingsWrite(({ task, daily }: { task: string; daily: string | null }) =>
    saveTaskCap(task, daily),
  );

/** Coût maximal d'une tâche de l'application (profil connu du serveur), relu à la demande. */
export const useTaskEstimate = (task: string, enabled = true) =>
  useQuery({
    queryKey: ["ai", "estimate", task],
    queryFn: () => estimateAICost({ task_type: task }),
    enabled,
    staleTime: 30_000,
    retry: false,
  });

export const useEstimateAICost = () => useMutation({ mutationFn: estimateAICost });

/** Un test passe par le journal : la consommation affichée doit être relue ensuite. */
export function useAITest() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: runAITest,
    onSettled: () => void client.invalidateQueries({ queryKey: AI_USAGE_KEY }),
  });
}
