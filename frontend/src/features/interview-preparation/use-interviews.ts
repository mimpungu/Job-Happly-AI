"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "@/services/api-client";
import {
  answerQuestion,
  completeSimulation,
  createInterview,
  deleteSimulation,
  draftFollowUp,
  generatePreparation,
  getPreparation,
  listInterviews,
  listSimulations,
  scheduleFollowUp,
  startSimulation,
  updateInterview,
} from "@/services/interviews";
import type { AssistMode, InterviewInput } from "@/types/interviews";

const key = (applicationId: string) => ["interview-preparation", applicationId] as const;
// Une candidature vue dans l'agenda ou le suivi change aussi quand un entretien est enregistré.
const crmKeys = [["applications"], ["dashboard"]] as const;

export function usePreparation(applicationId: string) {
  return useQuery({
    queryKey: [...key(applicationId), "preparation"],
    queryFn: async () => {
      try {
        return await getPreparation(applicationId);
      } catch (erreur) {
        // Pas encore préparée : état normal, pas une erreur.
        if (erreur instanceof ApiError && erreur.status === 404) return null;
        throw erreur;
      }
    },
  });
}

export const useSimulations = (applicationId: string) =>
  useQuery({
    queryKey: [...key(applicationId), "simulations"],
    queryFn: () => listSimulations(applicationId),
  });

export const useInterviews = (applicationId: string) =>
  useQuery({
    queryKey: [...key(applicationId), "interviews"],
    queryFn: () => listInterviews(applicationId),
  });

function useInvalidate(applicationId: string, withCrm = false) {
  const client = useQueryClient();
  return async () => {
    await client.invalidateQueries({ queryKey: key(applicationId) });
    if (withCrm) await Promise.all(crmKeys.map((k) => client.invalidateQueries({ queryKey: k })));
  };
}

export function useGeneratePreparation(applicationId: string) {
  const invalider = useInvalidate(applicationId);
  return useMutation({
    mutationFn: (mode: AssistMode) => generatePreparation(applicationId, mode),
    onSuccess: invalider,
  });
}

export function useStartSimulation(applicationId: string) {
  const invalider = useInvalidate(applicationId);
  return useMutation({
    mutationFn: (count: number) => startSimulation(applicationId, count),
    onSuccess: invalider,
  });
}

export function useAnswerQuestion(applicationId: string, simulationId: string) {
  const invalider = useInvalidate(applicationId);
  return useMutation({
    mutationFn: ({
      questionId,
      text,
      mode,
    }: {
      questionId: string;
      text: string;
      mode: AssistMode;
    }) => answerQuestion(simulationId, questionId, text, mode),
    onSuccess: invalider,
  });
}

export function useCompleteSimulation(applicationId: string) {
  const invalider = useInvalidate(applicationId);
  return useMutation({ mutationFn: completeSimulation, onSuccess: invalider });
}

export function useDeleteSimulation(applicationId: string) {
  const invalider = useInvalidate(applicationId);
  return useMutation({ mutationFn: deleteSimulation, onSuccess: invalider });
}

export function useSaveInterview(applicationId: string, interviewId?: string) {
  const invalider = useInvalidate(applicationId, true);
  return useMutation({
    mutationFn: (data: InterviewInput) =>
      interviewId ? updateInterview(interviewId, data) : createInterview(applicationId, data),
    onSuccess: invalider,
  });
}

export function useFollowUp(applicationId: string, interviewId: string) {
  const invalider = useInvalidate(applicationId, true);
  return {
    draft: useMutation({ mutationFn: () => draftFollowUp(interviewId), onSuccess: invalider }),
    schedule: useMutation({
      mutationFn: (at?: string) => scheduleFollowUp(interviewId, at),
      onSuccess: invalider,
    }),
  };
}
