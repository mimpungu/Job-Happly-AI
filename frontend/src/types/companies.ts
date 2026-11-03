/** Contrats de l'API des entreprises suivies et de la collecte (docs/API.md). */

export interface Company {
  id: string;
  name: string;
  careers_url: string | null;
  ats_kind: string | null;
  detection_status: "pending" | "supported" | "unsupported";
  enabled: boolean;
  last_checked_at: string | null;
  last_success_at: string | null;
  last_error: string | null;
}

export interface DiscoveredBoard {
  ats_kind: string;
  token: string;
  careers_url: string;
  board_name: string | null;
  offer_count: number;
}

export interface SourceOutcome {
  company_id: string;
  company_name: string;
  source_key: string;
  succeeded: boolean;
  complete: boolean;
  fetched: number;
  created: number;
  merged: number;
  changed: number;
  unchanged: number;
  rejected: number;
  expired: number;
  error_type: string | null;
}

export interface CollectionReport {
  started_at: string;
  finished_at: string;
  status: "succeeded" | "partial" | "failed";
  sources: SourceOutcome[];
}

export interface FranceTravailSearch {
  title: string | null;
  company: string | null;
  keywords: string[];
  city: string | null;
  department: string | null;
}

export interface FranceTravailResult {
  succeeded: boolean;
  complete: boolean;
  pages: number;
  fetched: number;
  created: number;
  merged: number;
  changed: number;
  unchanged: number;
  rejected: number;
  error_type: string | null;
}
