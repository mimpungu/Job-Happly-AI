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

export interface SourceSearchResult {
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
  enabled: boolean;
  requires_configuration: boolean;
  configured: boolean;
  status: "ok" | "error" | "unsupported" | "not_configured" | "never_checked";
  last_checked_at: string | null;
  last_success_at: string | null;
  last_error: string | null;
  offer_count: number;
}
