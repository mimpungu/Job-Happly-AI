import { filtersToSavedCriteria, parseTitles } from "@/features/jobs/filters";
import type { OfferFilters } from "@/types/jobs";
import type { DataSource, SourceSearchResult } from "@/types/sources";

import { apiFetch } from "./api-client";

export const listDataSources = () => apiFetch<DataSource[]>("/api/v1/sources");

/** Interroge les sources utiles en parallèle, puis lit les offres agrégées. */
export const searchSources = (filters: OfferFilters) =>
  apiFetch<SourceSearchResult>("/api/v1/search", {
    method: "POST",
    body: JSON.stringify({
      filter: filtersToSavedCriteria(filters),
      titles: parseTitles(filters.titles),
      refresh: true,
    }),
  });
