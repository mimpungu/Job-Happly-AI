/** Contrats de la recherche multi-sources et du catalogue des sources (docs/API.md). */

import type { OfferPage } from "./jobs";

export interface QueriedSource {
  source_key: string;
  source_name: string;
  status: "ok" | "failed";
  complete: boolean;
  fetched: number;
  created: number;
  merged: number;
  changed: number;
  unchanged: number;
  rejected: number;
  error_type: string | null;
}

export interface GeographicCoverage {
  requested: string[];
  /** Pays demandés qu'au moins une source interrogée déclare couvrir. */
  declared: string[];
  /** Pays demandés qu'aucune source interrogée ne déclare couvrir. */
  undeclared: string[];
  sources_without_declared_countries: string[];
}

export interface CompanySearch {
  /** `tracked`, `followed`, `candidates`, `not_found` ou `disabled`. */
  status: "tracked" | "followed" | "candidates" | "not_found" | "disabled";
  query: string;
  followed_name: string | null;
  boards: {
    ats_kind: string;
    token: string;
    careers_url: string;
    board_name: string | null;
    offer_count: number;
  }[];
}

export interface SourceSearchResult {
  /** Présent quand la recherche porte sur une entreprise précise. */
  company_search?: CompanySearch | null;
  coverage?: GeographicCoverage;
  /** Au moins une source interrogée ; sinon les résultats viennent de la base locale seule. */
  queried: boolean;
  status: "succeeded" | "partial" | "failed" | null;
  sources: QueriedSource[];
  results: OfferPage;
}

export interface DataSource {
  key: string;
  name: string;
  kind: string;
  countries: string[];
  /** Faux : la source ne déclare aucun pays, sa couverture n'est pas affirmée. */
  coverage_declared?: boolean;
  enabled: boolean;
  requires_configuration: boolean;
  configured: boolean;
  status: "ok" | "error" | "unsupported" | "not_configured" | "never_checked";
  last_checked_at: string | null;
  last_success_at: string | null;
  last_error: string | null;
  offer_count: number;
}
