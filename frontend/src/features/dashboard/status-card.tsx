import { Workflow } from "lucide-react";

import { cn } from "@/lib/cn";
import type { ApplicationStatus } from "@/types/application-status";

import { DashCard } from "./dash-card";
import { formatPercentValue } from "./format";
import { TrendChip } from "./trend-chip";

interface Groupe {
  key: string;
  label: string;
  statuses: readonly ApplicationStatus[];
  couleur: string;
}

const GROUPES: readonly Groupe[] = [
  {
    key: "preparation",
    label: "En préparation",
    statuses: ["new_offer", "to_analyze", "to_apply", "documents_to_prepare", "ready_to_send"],
    couleur: "bg-chart-1",
  },
  { key: "envoyees", label: "Envoyées", statuses: ["sent", "pending"], couleur: "bg-chart-2" },
  {
    key: "entretiens",
    label: "Entretiens",
    statuses: ["interview", "second_interview"],
    couleur: "bg-chart-3",
  },
  { key: "offres", label: "Offres reçues", statuses: ["offer_received"], couleur: "bg-chart-4" },
  {
    key: "closes",
    label: "Clôturées",
    statuses: ["rejected", "abandoned"],
    couleur: "bg-border-strong",
  },
];

export interface StatusCardProps {
  byStatus: Record<ApplicationStatus, number>;
  tracked: number;
  trackedPercent: number | null;
  interviews: number;
  sent: number;
  responseRate: number | null;
}

/** Répartition des candidatures par étape, avec une lecture du taux de réponse réel. */
export function StatusCard({
  byStatus,
  tracked,
  trackedPercent,
  interviews,
  sent,
  responseRate,
}: StatusCardProps) {
  const groupes = GROUPES.map((g) => ({
    ...g,
    total: g.statuses.reduce((somme, s) => somme + (byStatus[s] ?? 0), 0),
  }));
  const total = groupes.reduce((somme, g) => somme + g.total, 0);

  return (
    <DashCard
      title="Statut des candidatures"
      icon={Workflow}
      moreHref="/applications?vue=kanban"
      moreLabel="Ouvrir le Kanban"
      className="flex flex-col"
    >
      <dl className="mt-6 grid grid-cols-2 gap-4">
        <div>
          <dt className="text-sm text-foreground-muted">Candidatures suivies</dt>
          <dd className="mt-1 text-3xl font-semibold text-foreground">{tracked}</dd>
          <dd className="mt-2">
            <TrendChip percent={trackedPercent} period="ce mois-ci" />
          </dd>
        </div>
        <div className="border-l border-border pl-4">
          <dt className="text-sm text-foreground-muted">En entretien</dt>
          <dd className="mt-1 text-3xl font-semibold text-foreground">{interviews}</dd>
        </div>
      </dl>

      {total > 0 ? (
        <>
          <div
            role="img"
            aria-label={`Répartition : ${groupes
              .filter((g) => g.total > 0)
              .map((g) => `${g.label} ${g.total}`)
              .join(", ")}`}
            className="mt-6 flex h-3 w-full gap-0.5 overflow-hidden rounded-full"
          >
            {groupes
              .filter((g) => g.total > 0)
              .map((g) => (
                <span
                  key={g.key}
                  className={cn("h-full", g.couleur)}
                  style={{ width: `${(g.total / total) * 100}%` }}
                />
              ))}
          </div>
          <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm text-foreground-muted">
            {groupes
              .filter((g) => g.total > 0)
              .map((g) => (
                <li key={g.key} className="flex items-center gap-2">
                  <span aria-hidden="true" className={cn("size-2.5 rounded-full", g.couleur)} />
                  {g.label} · {g.total}
                </li>
              ))}
          </ul>
        </>
      ) : (
        <p className="mt-6 text-sm text-foreground-muted">
          Aucune candidature suivie : la répartition apparaît dès la première.
        </p>
      )}

      <p className="mt-auto flex gap-3 rounded-xl bg-background-secondary p-4 pt-4 text-sm text-foreground">
        <span aria-hidden="true" className="w-1 shrink-0 rounded-full bg-accent" />
        {responseRate === null
          ? "Aucune candidature envoyée : le taux de réponse sera calculé dès le premier envoi."
          : `Taux de réponse : ${formatPercentValue(responseRate)} (${sent} candidature${sent > 1 ? "s" : ""} envoyée${sent > 1 ? "s" : ""}).`}
      </p>
    </DashCard>
  );
}
