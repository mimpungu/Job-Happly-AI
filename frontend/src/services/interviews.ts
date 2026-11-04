import type {
  AssistMode,
  Interview,
  InterviewInput,
  Preparation,
  Simulation,
  SimulationAnswer,
} from "@/types/interviews";

import { apiFetch } from "./api-client";

const BASE = "/api/v1/interview-preparation";
const app = (id: string) => `${BASE}/applications/${encodeURIComponent(id)}`;
const json = (corps: unknown): RequestInit => ({ body: JSON.stringify(corps) });

export const getPreparation = (applicationId: string) =>
  apiFetch<Preparation>(`${app(applicationId)}/preparation`);

/** La génération n'est jamais automatique : elle suit un clic, avec le mode choisi. */
export const generatePreparation = (applicationId: string, mode: AssistMode) =>
  apiFetch<Preparation>(`${app(applicationId)}/preparation`, {
    method: "POST",
    ...json({ mode }),
  });

export const listSimulations = (applicationId: string) =>
  apiFetch<Simulation[]>(`${app(applicationId)}/simulations`);

export const startSimulation = (applicationId: string, questionCount: number) =>
  apiFetch<Simulation>(`${app(applicationId)}/simulations`, {
    method: "POST",
    ...json({ question_count: questionCount }),
  });

export const answerQuestion = (
  simulationId: string,
  questionId: string,
  text: string,
  mode: AssistMode,
) =>
  apiFetch<SimulationAnswer>(
    `${BASE}/simulations/${encodeURIComponent(simulationId)}/answers/${encodeURIComponent(questionId)}`,
    { method: "PUT", ...json({ text, mode }) },
  );

export const completeSimulation = (simulationId: string) =>
  apiFetch<Simulation>(`${BASE}/simulations/${encodeURIComponent(simulationId)}/complete`, {
    method: "POST",
  });

export const deleteSimulation = (simulationId: string) =>
  apiFetch<void>(`${BASE}/simulations/${encodeURIComponent(simulationId)}`, { method: "DELETE" });

export const listInterviews = (applicationId: string) =>
  apiFetch<Interview[]>(`${BASE}/interviews?application_id=${encodeURIComponent(applicationId)}`);

export const createInterview = (applicationId: string, data: InterviewInput) =>
  apiFetch<Interview>(`${app(applicationId)}/interviews`, { method: "POST", ...json(data) });

export const updateInterview = (id: string, data: InterviewInput) =>
  apiFetch<Interview>(`${BASE}/interviews/${encodeURIComponent(id)}`, {
    method: "PUT",
    ...json(data),
  });

export const draftFollowUp = (id: string) =>
  apiFetch<Interview>(`${BASE}/interviews/${encodeURIComponent(id)}/follow-up-draft`, {
    method: "POST",
    ...json({ language: "fr" }),
  });

export const scheduleFollowUp = (id: string, followUpAt?: string) =>
  apiFetch<{ follow_up_at: string }>(`${BASE}/interviews/${encodeURIComponent(id)}/follow-up`, {
    method: "POST",
    ...json(followUpAt ? { follow_up_at: followUpAt } : {}),
  });
