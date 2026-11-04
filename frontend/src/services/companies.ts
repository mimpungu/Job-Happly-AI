import type { CollectionReport, Company, DiscoveredBoard } from "@/types/companies";

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

export const runCollection = () =>
  apiFetch<CollectionReport>("/api/v1/collection/run", { method: "POST" });
