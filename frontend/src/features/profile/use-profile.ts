"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getProfile,
  importCv,
  listHistory,
  saveDraft,
  startNewVersion,
  validateProfile,
} from "@/services/profile";
import type { ProfileDocument, StoredProfile } from "@/types/profile";

export const PROFILE_KEY = ["profile"] as const;
const HISTORY_KEY = ["profile", "history"] as const;

export function useProfile() {
  return useQuery({ queryKey: PROFILE_KEY, queryFn: getProfile });
}

export function useProfileHistory(actif: boolean) {
  return useQuery({ queryKey: HISTORY_KEY, queryFn: listHistory, enabled: actif });
}

/** Après une écriture, le serveur est la source de vérité : on met le cache à jour et on relit le journal. */
function useProfileWrite<V>(ecrire: (valeur: V) => Promise<StoredProfile>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ecrire,
    onSuccess: (stocke) => {
      client.setQueryData(PROFILE_KEY, stocke);
      void client.invalidateQueries({ queryKey: HISTORY_KEY });
    },
  });
}

export const useSaveDraft = () =>
  useProfileWrite((document: ProfileDocument) => saveDraft(document));
export const useValidateProfile = () => useProfileWrite(() => validateProfile());
export const useNewVersion = () => useProfileWrite(() => startNewVersion());

export function useImportCv() {
  return useMutation({ mutationFn: (fichier: File) => importCv(fichier) });
}
