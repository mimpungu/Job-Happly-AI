/** Contrats de l'API des offres (voir docs/API.md). Les montants arrivent en chaînes décimales. */

export type OfferState = "saved" | "ignored";
export type StateFilter = "visible" | "saved" | "ignored" | "all";

export type OfferSort =
  | "published_desc"
  | "published_asc"
  | "title_asc"
  | "company_asc"
  | "salary_desc"
  | "recently_seen"
  | "score_desc";

export interface OfferSummary {
  id: string;
  title: string;
  company_name: string | null;
  location: string | null;
  country_code: string | null;
  employment_type: string | null;
  remote_type: string | null;
  salary_min: string | null;
  salary_max: string | null;
  salary_currency: string | null;
  published_at: string | null;
  status: string;
  state: OfferState | null;
  source_keys: string[];
  /** Score de compatibilité (0-100, indicatif) ; `null` = pas encore évalué. */
  match_score: string | null;
  match_reliability: "high" | "medium" | "low" | null;
}

export interface OfferSourceView {
  source_key: string;
  source_name: string;
  source_url: string | null;
  last_seen_at: string;
  still_listed: boolean;
}

export interface OfferDetail {
  summary: OfferSummary;
  description: string;
  application_url: string;
  language: string | null;
  expires_at: string | null;
  first_seen_at: string;
  last_seen_at: string;
  sources: OfferSourceView[];
}

export interface OfferPage {
  items: OfferSummary[];
  total: number;
  page: number;
  page_size: number;
  page_count: number;
}

/** Filtres de la liste, tels que l'utilisateur les saisit (tout est facultatif). */
export interface OfferFilters {
  text: string;
  company: string;
  city: string;
  country: string;
  employmentType: string;
  remoteType: string;
  salaryMin: string;
  salaryCurrency: string;
  /** Date `AAAA-MM-JJ` : une date absolue rend la recherche reproductible une fois sauvegardée. */
  publishedSince: string;
  /** Compatibilité minimale (0-100) ; vide = pas de filtre. */
  minScore: string;
  sort: OfferSort;
  state: StateFilter;
  page: number;
}

export interface SavedSearch {
  id: string;
  name: string;
  offer_filter: Record<string, unknown>;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SearchRun {
  id: string;
  saved_search_id: string | null;
  offer_filter: Record<string, unknown>;
  status: string;
  started_at: string;
  finished_at: string | null;
  result_count: number | null;
}

export interface ApiErrorBody {
  error: { code: string; message: string; details?: { field: string; message: string }[] };
}

/** Offre saisie à la main (copiée depuis un site). */
export interface ManualOfferInput {
  title: string;
  company_name: string | null;
  location: string | null;
  application_url: string;
  description: string;
}

export interface ManualOfferResult {
  offer_id: string;
  created: boolean;
  merged: boolean;
  changed: boolean;
  already_known: boolean;
}
