"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  addContact,
  addInterview,
  addNote,
  attachDocuments,
  changeStatus,
  confirmSubmission,
  createApplication,
  deleteApplication,
  getApplication,
  getApplicationStats,
  getDashboard,
  getDossier,
  getKanban,
  listApplications,
  listDocumentChoices,
  setFollowUp,
} from "@/services/applications";
import type { ApplicationStatus } from "@/types/application-status";
import type { ApplicationFilters } from "@/types/applications";

export const applicationsKey = ["applications"] as const;
export const dashboardKey = ["dashboard"] as const;

export function useApplications(filters: ApplicationFilters, enabled = true) {
  return useQuery({
    queryKey: [...applicationsKey, "list", filters],
    queryFn: () => listApplications(filters),
    enabled,
    // Garde la page précédente affichée pendant le chargement de la suivante.
    placeholderData: (precedent) => precedent,
  });
}

export const useKanban = (enabled = true) =>
  useQuery({ queryKey: [...applicationsKey, "kanban"], queryFn: getKanban, enabled });

export const useApplicationStats = () =>
  useQuery({ queryKey: [...applicationsKey, "stats"], queryFn: getApplicationStats });

export const useApplication = (id: string) =>
  useQuery({ queryKey: [...applicationsKey, "detail", id], queryFn: () => getApplication(id) });

export const useDossier = (id: string) =>
  useQuery({ queryKey: [...applicationsKey, "dossier", id], queryFn: () => getDossier(id) });

export const useDocumentChoices = () =>
  useQuery({ queryKey: [...applicationsKey, "documents"], queryFn: listDocumentChoices });

export const useDashboard = () => useQuery({ queryKey: dashboardKey, queryFn: getDashboard });

/** Après toute écriture, le serveur reste la source de vérité : on relit listes, fiches et tableau de bord. */
function useInvalidate() {
  const client = useQueryClient();
  return () =>
    Promise.all([
      client.invalidateQueries({ queryKey: applicationsKey }),
      client.invalidateQueries({ queryKey: dashboardKey }),
    ]);
}

export function useCreateApplication() {
  const invalider = useInvalidate();
  return useMutation({
    mutationFn: (offerId: string) => createApplication(offerId),
    onSuccess: invalider,
  });
}

export function useDeleteApplication() {
  const invalider = useInvalidate();
  return useMutation({ mutationFn: (id: string) => deleteApplication(id), onSuccess: invalider });
}

export function useChangeStatus(id: string) {
  const invalider = useInvalidate();
  return useMutation({
    mutationFn: ({ target, reason }: { target: ApplicationStatus; reason?: string }) =>
      changeStatus(id, target, reason),
    onSuccess: invalider,
  });
}

export function useConfirmSubmission(id: string) {
  const invalider = useInvalidate();
  return useMutation({
    mutationFn: (input: { notes?: string; appliedAt?: string }) => confirmSubmission(id, input),
    onSuccess: invalider,
  });
}

export function useAddNote(id: string) {
  const invalider = useInvalidate();
  return useMutation({ mutationFn: (body: string) => addNote(id, body), onSuccess: invalider });
}

export function useAddInterview(id: string) {
  const invalider = useInvalidate();
  return useMutation({
    mutationFn: ({ description, time }: { description: string; time?: string }) =>
      addInterview(id, description, time),
    onSuccess: invalider,
  });
}

export function useSetFollowUp(id: string) {
  const invalider = useInvalidate();
  return useMutation({
    mutationFn: ({ at, notes }: { at: string | null; notes?: string }) =>
      setFollowUp(id, at, notes),
    onSuccess: invalider,
  });
}

export function useAddContact(id: string) {
  const invalider = useInvalidate();
  return useMutation({
    mutationFn: (contact: { name: string; email?: string; phone?: string; role?: string }) =>
      addContact(id, contact),
    onSuccess: invalider,
  });
}

export function useAttachDocuments(id: string) {
  const invalider = useInvalidate();
  return useMutation({
    mutationFn: (versions: { cvVersionId?: string; letterVersionId?: string }) =>
      attachDocuments(id, versions),
    onSuccess: invalider,
  });
}
