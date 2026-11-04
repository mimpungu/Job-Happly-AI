import type { CriterionKey, MatchKind, Reliability } from "@/types/matching";

export const CRITERION_LABELS: Record<CriterionKey, string> = {
  job_title: "Métier",
  skills: "Compétences",
  experience: "Expérience",
  education: "Formation",
  location: "Localisation",
  contract: "Contrat",
  salary: "Salaire",
  remote: "Télétravail",
  freshness: "Ancienneté de l'annonce",
  mandatory_requirements: "Exigences obligatoires",
};

export const RELIABILITY_LABELS: Record<Reliability, string> = {
  high: "Fiabilité élevée",
  medium: "Fiabilité moyenne",
  low: "Fiabilité faible",
};

export const KIND_LABELS: Record<MatchKind, string> = {
  present: "Présente",
  partial: "Partielle",
  absent: "Absente de votre profil",
  unverifiable: "À évaluer vous-même",
};

export type Band = "good" | "fair" | "low";

/** Tranches d'affichage d'un score (0-100) : un repère de lecture, pas un seuil d'embauche. */
export function bandOf(score: number): Band {
  if (score >= 70) return "good";
  return score >= 40 ? "fair" : "low";
}

export const BAND_LABELS: Record<Band, string> = {
  good: "Bonne compatibilité",
  fair: "Compatibilité moyenne",
  low: "Faible compatibilité",
};
