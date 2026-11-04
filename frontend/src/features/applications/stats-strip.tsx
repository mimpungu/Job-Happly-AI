import { Skeleton } from "@/components/ui/skeleton";
import type { ApplicationStats } from "@/types/applications";

import { formatPercent } from "./format";

export function StatsStrip({ stats }: { stats: ApplicationStats | undefined }) {
  if (!stats) return <Skeleton className="h-16 w-full" />;
  const cartes = [
    { label: "Candidatures", valeur: String(stats.total_applications) },
    { label: "Envoyées", valeur: String(stats.sent_applications) },
    { label: "Entretiens", valeur: String(stats.interviews_count) },
    {
      label: "Taux de réponse",
      valeur: formatPercent(stats.response_rate),
      aide: stats.response_rate === null ? "Aucune candidature envoyée" : undefined,
    },
    { label: "Relances échues", valeur: String(stats.due_follow_ups_count) },
  ];
  return (
    <dl className="grid grid-cols-2 gap-3 md:grid-cols-5" aria-label="Statistiques de suivi">
      {cartes.map((c) => (
        <div key={c.label} className="rounded-lg border border-border bg-surface px-4 py-3">
          <dt className="text-xs text-foreground-muted">{c.label}</dt>
          <dd className="text-xl font-semibold text-foreground">{c.valeur}</dd>
          {c.aide ? <dd className="text-xs text-foreground-muted">{c.aide}</dd> : null}
        </div>
      ))}
    </dl>
  );
}
