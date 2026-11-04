"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getProfile,
  getVersion,
  importCv,
  listHistory,
  listVersions,
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

/** Versions disponibles, de la plus récente à la plus ancienne. */
export function useVersions() {
  return useQuery({ queryKey: [...PROFILE_KEY, "versions"], queryFn: listVersions });
}

/** Contenu d'une version précise (consultation en lecture seule). */
export function useVersion(version: number | null) {
  return useQuery({
    queryKey: [...PROFILE_KEY, "version", version],
    queryFn: () => getVersion(version as number),
    enabled: version !== null,
  });
}

/** Après une écriture, le serveur est la source de vérité : on met le cache à jour et on relit le journal. */
function useProfileWrite<V>(ecrire: (valeur: V) => Promise<StoredProfile>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ecrire,
    onSuccess: (stocke) => {
      client.setQueryData(PROFILE_KEY, stocke);
      void client.invalidateQueries({ queryKey: HISTORY_KEY });
      // Une version vient d'être créée ou validée : la liste des versions n'est plus à jour.
      void client.invalidateQueries({ queryKey: [...PROFILE_KEY, "versions"] });
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
