/** Contrats de l'API de correspondance (voir docs/API.md). Les nombres décimaux sont des chaînes. */

export type CriterionKey =
  | "job_title"
  | "skills"
  | "experience"
  | "education"
  | "location"
  | "contract"
  | "salary"
  | "remote"
  | "freshness"
  | "mandatory_requirements";

/** Statut d'un élément comparé : « absent » n'est jamais « incompétent ». */
export type MatchKind = "present" | "partial" | "absent" | "unverifiable";
export type Reliability = "high" | "medium" | "low";

export interface MatchItem {
  kind: MatchKind;
  label: string;
  detail: string | null;
  criterion: CriterionKey | null;
}

export interface CriterionResult {
  criterion: CriterionKey;
  /** `missing_data` : le critère n'est pas compté (ce n'est pas un échec). */
  status: "evaluated" | "missing_data";
  weight: string;
  score: string | null;
  explanation: string;
  items: MatchItem[];
  uncertain: boolean;
}

export interface MatchResult {
  score: string | null;
  coverage: string;
  reliability: Reliability;
  weights_version: string;
  criteria: CriterionResult[];
  matches: MatchItem[];
  gaps: MatchItem[];
  summary: string;
  disclaimer: string;
}

export interface MatchResponse {
  result: MatchResult;
  profile_version: number;
  computed_at: string;
}

export interface CriterionWeight {
  key: CriterionKey;
  label: string;
  weight: string;
  default_weight: string;
}

export interface WeightsResponse {
  criteria: CriterionWeight[];
  version: string;
  is_default: boolean;
}

export interface RecomputeReport {
  computed: number;
  not_computable: number;
  profile_version: number;
  weights_version: string;
}
