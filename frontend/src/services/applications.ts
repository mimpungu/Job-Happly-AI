import type {
  ApplicationDetail,
  ApplicationFilters,
  ApplicationItem,
  ApplicationPage,
  ApplicationStats,
  Contact,
  DashboardMetrics,
  DocumentChoice,
  Dossier,
  GeneratedDocumentRef,
  KanbanView,
  TimelineEvent,
} from "@/types/applications";
import type { ApplicationStatus } from "@/types/application-status";

import { apiFetch } from "./api-client";

export const APPLICATIONS_PAGE_SIZE = 25;
export const KANBAN_COLUMN_LIMIT = 20;

const base = (id: string) => `/api/v1/applications/${encodeURIComponent(id)}`;
const json = (corps: unknown): RequestInit => ({ body: JSON.stringify(corps) });

/** Filtres de l'interface → paramètres de requête ; un filtre vide ne restreint rien. */
export function filtersToQuery(filters: ApplicationFilters): string {
  const q = new URLSearchParams();
  if (filters.status) q.set("status", filters.status);
  if (filters.company.trim()) q.set("company", filters.company.trim());
  if (filters.title.trim()) q.set("title", filters.title.trim());
  if (filters.followUp === "planned") q.set("has_follow_up", "true");
  if (filters.followUp === "due") q.set("follow_up_due", "true");
  q.set("limit", String(APPLICATIONS_PAGE_SIZE));
  q.set("offset", String((Math.max(filters.page, 1) - 1) * APPLICATIONS_PAGE_SIZE));
  return q.toString();
}

export const listApplications = (filters: ApplicationFilters) =>
  apiFetch<ApplicationPage>(`/api/v1/applications?${filtersToQuery(filters)}`);

export const getKanban = () =>
  apiFetch<KanbanView>(`/api/v1/applications/kanban?per_column_limit=${KANBAN_COLUMN_LIMIT}`);

export const getApplicationStats = () => apiFetch<ApplicationStats>("/api/v1/applications/stats");

export const getApplication = (id: string) => apiFetch<ApplicationDetail>(base(id));

export const createApplication = (offerId: string, initialStatus: ApplicationStatus = "to_apply") =>
  apiFetch<ApplicationItem>("/api/v1/applications", {
    method: "POST",
    ...json({ offer_id: offerId, initial_status: initialStatus }),
  });

export const changeStatus = (id: string, target: ApplicationStatus, reason?: string) =>
  apiFetch<ApplicationDetail>(`${base(id)}/status`, {
    method: "PATCH",
    ...json({ target_status: target, ...(reason ? { reason } : {}) }),
  });

/** Trace d'un envoi fait par l'utilisateur ; le serveur n'envoie jamais rien lui-même. */
export const confirmSubmission = (id: string, input: { notes?: string; appliedAt?: string }) =>
  apiFetch<ApplicationDetail>(`${base(id)}/confirm-submission`, {
    method: "POST",
    ...json({
      ...(input.notes ? { notes: input.notes } : {}),
      ...(input.appliedAt ? { applied_at: input.appliedAt } : {}),
    }),
  });

export const addNote = (id: string, body: string) =>
  apiFetch<TimelineEvent>(`${base(id)}/notes`, { method: "POST", ...json({ body }) });

export const addInterview = (id: string, description: string, interviewTime?: string) =>
  apiFetch<TimelineEvent>(`${base(id)}/interviews`, {
    method: "POST",
    ...json({ description, ...(interviewTime ? { interview_time: interviewTime } : {}) }),
  });

export const setFollowUp = (id: string, followUpAt: string | null, notes?: string) =>
  apiFetch<ApplicationDetail>(`${base(id)}/follow-up`, {
    method: "PATCH",
    ...json({ follow_up_at: followUpAt, ...(notes ? { notes } : {}) }),
  });

export const addContact = (
  id: string,
  contact: { name: string; email?: string; phone?: string; role?: string },
) => apiFetch<Contact>(`${base(id)}/contacts`, { method: "POST", ...json(contact) });

export const attachDocuments = (
  id: string,
  versions: { cvVersionId?: string; letterVersionId?: string },
) =>
  apiFetch<ApplicationDetail>(`${base(id)}/documents`, {
    method: "PUT",
    ...json({
      cv_version_id: versions.cvVersionId ?? null,
      letter_version_id: versions.letterVersionId ?? null,
    }),
  });

export const getDossier = (id: string) => apiFetch<Dossier>(`${base(id)}/dossier`);

export const getApplicationUrl = (id: string) =>
  apiFetch<{ application_url: string }>(`${base(id)}/open-url`);

export const getDashboard = () => apiFetch<DashboardMetrics>("/api/v1/dashboard");

/** Versions de CV et de lettres proposables à l'association, de la plus récente à la plus ancienne. */
export async function listDocumentChoices(): Promise<DocumentChoice[]> {
  const [cvs, lettres] = await Promise.all([
    apiFetch<GeneratedDocumentRef[]>("/api/v1/resumes"),
    apiFetch<GeneratedDocumentRef[]>("/api/v1/cover-letters"),
  ]);
  const choix = (docs: GeneratedDocumentRef[], kind: DocumentChoice["kind"]) =>
    docs.flatMap((d) =>
      [...d.versions]
        .sort((a, b) => b.version - a.version)
        .map((v) => ({ versionId: v.id, kind, label: `${d.title} — v${v.version}` })),
    );
  return [...choix(cvs, "cv"), ...choix(lettres, "cover_letter")];
}
