import type { NotificationPreferences } from "@/types/notifications";

import { apiFetch } from "./api-client";

export const getNotificationPreferences = () =>
  apiFetch<NotificationPreferences>("/api/v1/notifications/preferences");

/** Seuls les champs fournis changent : le serveur conserve les autres. */
export const saveNotificationPreferences = (corps: Partial<NotificationPreferences>) =>
  apiFetch<NotificationPreferences>("/api/v1/notifications/preferences", {
    method: "PUT",
    body: JSON.stringify(corps),
  });
