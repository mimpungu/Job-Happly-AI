import { APPLICATION_STATUSES, type ApplicationStatus } from "@/types/application-status";
import type { ApplicationFilters } from "@/types/applications";

export type ApplicationView = "table" | "kanban";

export const EMPTY_FILTERS: ApplicationFilters = {
  status: "",
  company: "",
  title: "",
  followUp: "",
  page: 1,
};

/** L'URL est la source de vérité : une valeur inconnue est ignorée plutôt que transmise au serveur. */
export function filtersFromParams(params: URLSearchParams): ApplicationFilters {
  const statut = params.get("status") ?? "";
  const relance = params.get("relance") ?? "";
  const page = Number.parseInt(params.get("page") ?? "1", 10);
  return {
    status: (APPLICATION_STATUSES as readonly string[]).includes(statut)
      ? (statut as ApplicationStatus)
      : "",
    company: params.get("company") ?? "",
    title: params.get("title") ?? "",
    followUp: relance === "planned" || relance === "due" ? relance : "",
    page: Number.isFinite(page) && page >= 1 ? page : 1,
  };
}

export function viewFromParams(params: URLSearchParams): ApplicationView {
  return params.get("vue") === "kanban" ? "kanban" : "table";
}

export function filtersToParams(
  filters: ApplicationFilters,
  view: ApplicationView,
): URLSearchParams {
  const q = new URLSearchParams();
  if (view === "kanban") q.set("vue", "kanban");
  if (filters.status) q.set("status", filters.status);
  if (filters.company.trim()) q.set("company", filters.company.trim());
  if (filters.title.trim()) q.set("title", filters.title.trim());
  if (filters.followUp) q.set("relance", filters.followUp);
  if (filters.page > 1) q.set("page", String(filters.page));
  return q;
}

export const FOLLOW_UP_OPTIONS = [
  { value: "planned", label: "Relance planifiée" },
  { value: "due", label: "Relance échue" },
] as const;
