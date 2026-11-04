/** Contrats de l'analyse d'offre (docs/API.md). Tout est lu dans le texte de l'annonce. */

export interface LanguageRequirement {
  language: string;
  level: string | null;
  mandatory: boolean;
  evidence: string;
}

export interface Mobility {
  visa: "sponsorship_offered" | "no_sponsorship" | "work_authorization_required" | null;
  relocation_offered: boolean;
  travel: string | null;
  evidence: string[];
}

export interface OfferAnalysis {
  version: string;
  missions: string[];
  mandatory_skills: string[];
  expected_skills: string[];
  desired_skills: string[];
  technologies: string[];
  years_experience: number | null;
  years_mandatory: boolean | null;
  languages: LanguageRequirement[];
  mobility: Mobility;
  missing: { code: string; label: string }[];
  summary: string | null;
}

export interface AnalysisResponse {
  analysis_id: string;
  computed_at: string;
  reused: boolean;
  analysis: OfferAnalysis;
}

export interface AISummary {
  summary: string;
  key_points: string[];
  provider: string;
  model: string;
  cache_hit: boolean;
  cost: string;
}
