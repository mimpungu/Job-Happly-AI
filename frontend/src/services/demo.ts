import { apiFetch } from "./api-client";

export interface DemoStatus {
  enabled: boolean;
  offers: number;
  applications: number;
  notice: string;
}

export const getDemo = () => apiFetch<DemoStatus>("/api/v1/demo");
export const enableDemo = () => apiFetch<DemoStatus>("/api/v1/demo/enable", { method: "POST" });
export const disableDemo = () => apiFetch<DemoStatus>("/api/v1/demo/disable", { method: "POST" });
