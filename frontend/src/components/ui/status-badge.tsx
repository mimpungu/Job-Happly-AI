import type { ApplicationStatus } from "@/types/application-status";

import { Badge, type BadgeProps } from "./badge";

const STATUS_DISPLAY: Record<ApplicationStatus, { label: string; variant: BadgeProps["variant"] }> =
  {
    new_offer: { label: "Nouvelle offre", variant: "neutral" },
    to_analyze: { label: "À analyser", variant: "neutral" },
    to_apply: { label: "À postuler", variant: "accent" },
    documents_to_prepare: { label: "Documents à préparer", variant: "accent" },
    ready_to_send: { label: "Prête à envoyer", variant: "accent" },
    sent: { label: "Envoyée", variant: "accent" },
    pending: { label: "En attente", variant: "warning" },
    interview: { label: "Entretien", variant: "warning" },
    second_interview: { label: "Deuxième entretien", variant: "warning" },
    offer_received: { label: "Offre reçue", variant: "success" },
    rejected: { label: "Refus", variant: "danger" },
    abandoned: { label: "Abandonnée", variant: "neutral" },
  };

export const statusLabel = (status: ApplicationStatus): string => STATUS_DISPLAY[status].label;

/** Le statut est toujours exprimé par un texte, jamais par la seule couleur. */
export function StatusBadge({ status }: { status: ApplicationStatus }) {
  const { label, variant } = STATUS_DISPLAY[status];
  return <Badge variant={variant}>{label}</Badge>;
}
