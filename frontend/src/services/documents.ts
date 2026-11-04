import { env } from "@/lib/env";
import type { CoverLetter, LetterRequest, ResumeDocument, ResumeRequest } from "@/types/documents";

import { apiFetch } from "./api-client";

const post = (corps: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(corps) });

export const listResumes = () => apiFetch<ResumeDocument[]>("/api/v1/resumes");

export const generateResume = (r: ResumeRequest) =>
  apiFetch<ResumeDocument>("/api/v1/resumes/generate", post(r));

export const listLetters = () => apiFetch<CoverLetter[]>("/api/v1/cover-letters");

export const generateLetter = (r: LetterRequest) =>
  apiFetch<CoverLetter>("/api/v1/cover-letters/generate", post(r));

/** Liens de téléchargement directs : le navigateur enregistre le fichier, rien ne transite par le code. */
export function downloadUrl(
  kind: "resumes" | "cover-letters",
  id: string,
  version: number,
  format: "pdf" | "latex",
): string {
  return `${env.apiUrl}/api/v1/${kind}/${encodeURIComponent(id)}/versions/${version}/${format}`;
}
