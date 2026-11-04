import { TrendChip } from "./trend-chip";

interface StatCardProps {
  label: string;
  value: number;
  percent: number | null;
  period: string;
}

function StatCard({ label, value, percent, period }: StatCardProps) {
  return (
    <div className="flex flex-col justify-between gap-5 rounded-xl border border-border bg-shell px-6 py-5">
      <dt className="text-base text-foreground-muted">{label}</dt>
      <dd className="flex flex-wrap items-end justify-between gap-x-4 gap-y-2">
        <span className="text-4xl font-semibold text-foreground">{value}</span>
        <TrendChip percent={percent} period={period} />
      </dd>
    </div>
  );
}

export interface StatCardsProps {
  activeOffers: { value: number; percent: number | null };
  activeApplications: { value: number; percent: number | null };
  interviewsThisWeek: { value: number; percent: number | null };
}

/** Trois indicateurs avec leur variation réelle ; sans période de référence, aucune variation. */
export function StatCards({
  activeOffers,
  activeApplications,
  interviewsThisWeek,
}: StatCardsProps) {
  return (
    <dl className="grid gap-4 sm:grid-cols-3" aria-label="Indicateurs clés">
      <StatCard
        label="Offres actives"
        value={activeOffers.value}
        percent={activeOffers.percent}
        period="ce mois-ci"
      />
      <StatCard
        label="Candidatures en cours"
        value={activeApplications.value}
        percent={activeApplications.percent}
        period="ce mois-ci"
      />
      <StatCard
        label="Entretiens cette semaine"
        value={interviewsThisWeek.value}
        percent={interviewsThisWeek.percent}
        period="vs sem. dernière"
      />
    </dl>
  );
}
