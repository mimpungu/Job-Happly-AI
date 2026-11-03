import { filtersToApiQuery, filtersToSavedCriteria } from "@/features/jobs/filters";
import type {
  OfferDetail,
  OfferFilters,
  OfferPage,
  ManualOfferInput,
  ManualOfferResult,
  OfferState,
  SavedSearch,
  SearchRun,
} from "@/types/jobs";

import { apiFetch } from "./api-client";

export const PAGE_SIZE = 25;

export const listOffers = (filters: OfferFilters) =>
  apiFetch<OfferPage>(`/api/v1/offers?${filtersToApiQuery(filters, PAGE_SIZE)}`);

export const getOffer = (id: string) =>
  apiFetch<OfferDetail>(`/api/v1/offers/${encodeURIComponent(id)}`);

export const setOfferState = (id: string, state: OfferState | null) =>
  apiFetch<void>(`/api/v1/offers/${encodeURIComponent(id)}/state`, {
    method: "PUT",
    body: JSON.stringify({ state }),
  });

export const listSavedSearches = () => apiFetch<SavedSearch[]>("/api/v1/saved-searches");

export const createSavedSearch = (name: string, filters: OfferFilters) =>
  apiFetch<SavedSearch>("/api/v1/saved-searches", {
    method: "POST",
    body: JSON.stringify({ name, filter: filtersToSavedCriteria(filters) }),
  });

export const deleteSavedSearch = (id: string) =>
  apiFetch<void>(`/api/v1/saved-searches/${encodeURIComponent(id)}`, { method: "DELETE" });

/** Relance côté serveur : inscrit l'exécution à l'historique. */
export const runSavedSearch = (id: string) =>
  apiFetch<{ run: SearchRun; results: OfferPage }>(
    `/api/v1/saved-searches/${encodeURIComponent(id)}/run`,
    { method: "POST" },
  );

export const listSearchRuns = () => apiFetch<SearchRun[]>("/api/v1/search-runs?limit=10");

export const addManualOffer = (offre: ManualOfferInput) =>
  apiFetch<ManualOfferResult>("/api/v1/offers/manual", {
    method: "POST",
    body: JSON.stringify(offre),
  });
