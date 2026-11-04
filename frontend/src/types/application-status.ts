/** Statuts d'une candidature (spécification §12). */
export const APPLICATION_STATUSES = [
  "new_offer",
  "to_analyze",
  "to_apply",
  "documents_to_prepare",
  "ready_to_send",
  "sent",
  "pending",
  "interview",
  "second_interview",
  "offer_received",
  "rejected",
  "abandoned",
] as const;

export type ApplicationStatus = (typeof APPLICATION_STATUSES)[number];
