import type {
  CollectionReport,
  Company,
  DiscoveredBoard,
  FranceTravailResult,
  FranceTravailSearch,
} from "@/types/companies";

import { apiFetch } from "./api-client";

export const listCompanies = () => apiFetch<Company[]>("/api/v1/target-companies");

export const discoverCompany = (name: string) =>
  apiFetch<DiscoveredBoard[]>("/api/v1/target-companies/discover", {
    method: "POST",
    body: JSON.stringify({ name }),
  });

export const addCompany = (body: { name: string; careers_url: string | null; enabled: boolean }) =>
  apiFetch<Company>("/api/v1/target-companies", { method: "POST", body: JSON.stringify(body) });

export const setCompanyEnabled = (id: string, enabled: boolean) =>
  apiFetch<Company>(`/api/v1/target-companies/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify({ enabled }),
  });

export interface CollectionFilter {
  it_only: boolean;
  city: string | null;
}

export const runCollection = (filtre: CollectionFilter) =>
  apiFetch<CollectionReport>("/api/v1/collection/run", {
    method: "POST",
    body: JSON.stringify(filtre),
  });

export const getFranceTravailStatus = () =>
  apiFetch<{ configured: boolean }>("/api/v1/france-travail/status");

export const searchFranceTravail = (recherche: FranceTravailSearch) =>
  apiFetch<FranceTravailResult>("/api/v1/france-travail/search", {
    method: "POST",
    body: JSON.stringify(recherche),
  });
