import type { ChangeRecord, CvImportResult, ProfileDocument, StoredProfile } from "@/types/profile";

import { apiFetch } from "./api-client";

export const getProfile = () => apiFetch<StoredProfile | null>("/api/v1/profile");

export const saveDraft = (document: ProfileDocument) =>
  apiFetch<StoredProfile>("/api/v1/profile/draft", {
    method: "PUT",
    body: JSON.stringify(document),
  });

export const validateProfile = () =>
  apiFetch<StoredProfile>("/api/v1/profile/validate", { method: "POST" });

export const startNewVersion = () =>
  apiFetch<StoredProfile>("/api/v1/profile/versions", { method: "POST" });

export const listHistory = () => apiFetch<ChangeRecord[]>("/api/v1/profile/history?limit=100");

/** Envoie un CV pour lecture. Le fichier n'est pas conservé côté serveur. */
export function importCv(fichier: File) {
  const formulaire = new FormData();
  formulaire.append("fichier", fichier);
  return apiFetch<CvImportResult>("/api/v1/profile/import", { method: "POST", body: formulaire });
}
