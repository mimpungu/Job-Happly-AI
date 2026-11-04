"use client";

import { ServerCrash } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useDashboard } from "@/features/applications/use-applications";
import { PageHeading } from "@/features/shell/page-heading";
import type { DashboardMetrics } from "@/types/applications";

import { ActivityCard } from "./activity-card";
import { ExtrasRow } from "./extras-row";
import { FunnelCard } from "./funnel-card";
import { InterviewsCard } from "./interviews-card";
import { StatCards } from "./stat-cards";
import { StatusCard } from "./status-card";
import { TopMatchesCard } from "./top-matches-card";
import { countInWeek, weeklyPercent } from "./week";

export { formatMoney } from "./format";

function Greeting({ name }: { name: string | null }) {
  return (
    <PageHeading
      title={
        <>
          Bon retour{name ? `, ${name}` : ""} <span aria-hidden="true">👋</span>
        </>
      }
      subtitle="Voici où en est votre recherche d'emploi."
    />
  );
}

function Content({ metrics, now: fourni }: { metrics: DashboardMetrics; now?: Date }) {
  // Instant figé au premier rendu des données (client uniquement) : jamais lu au prérendu.
  const [now] = useState(() => fourni ?? new Date());
  const instants = metrics.interviews.map((i) => i.occurred_at);
  const cetteSemaine = countInWeek(instants, now);
  const laPrecedente = countInWeek(instants, now, -1);

  return (
    <div className="flex flex-col gap-5">
      <div className="grid gap-5 xl:grid-cols-[minmax(0,5fr)_minmax(0,10fr)]">
        <div className="flex min-w-0 flex-col gap-5">
          <TopMatchesCard
            matches={metrics.top_matches}
            scoredOffers={metrics.relevant_offers_count === null ? null : 1}
          />
          <InterviewsCard interviews={metrics.interviews} now={now} />
        </div>
        <div className="flex min-w-0 flex-col gap-5">
          <StatCards
            activeOffers={{
              value: metrics.active_offers_count,
              percent: metrics.active_offers_trend.percent,
            }}
            activeApplications={{
              value: metrics.active_applications_count,
              percent: metrics.applications_trend.percent,
            }}
            interviewsThisWeek={{
              value: cetteSemaine,
              percent: weeklyPercent(cetteSemaine, laPrecedente),
            }}
          />
          <FunnelCard funnel={metrics.funnel} />
          <div className="grid gap-5 md:grid-cols-2">
            <StatusCard
              byStatus={metrics.applications_by_status}
              tracked={metrics.funnel.tracked}
              trackedPercent={metrics.applications_trend.percent}
              interviews={metrics.interviews_count}
              sent={metrics.applications_sent_count}
              responseRate={metrics.response_rate}
            />
            <ActivityCard activities={metrics.recent_activities} now={now} />
          </div>
        </div>
      </div>
      <ExtrasRow
        totalOffers={metrics.total_offers_found}
        newOffers={metrics.new_offers_count}
        relevantOffers={metrics.relevant_offers_count}
        relevanceThreshold={metrics.relevance_threshold}
        budget={metrics.ai_budget}
        searches={metrics.recent_searches}
      />
    </div>
  );
}

export function DashboardView({ now }: { now?: Date }) {
  const tableau = useDashboard();
  return (
    <>
      <Greeting name={tableau.data?.display_name ?? null} />
      {tableau.isPending ? (
        <div
          className="flex flex-col gap-4"
          role="status"
          aria-label="Chargement du tableau de bord"
        >
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-96 w-full" />
        </div>
      ) : tableau.isError ? (
        <EmptyState
          icon={ServerCrash}
          title="Impossible de charger le tableau de bord"
          description={tableau.error.message}
          action={<Button onClick={() => void tableau.refetch()}>Réessayer</Button>}
        />
      ) : (
        <Content metrics={tableau.data} now={now} />
      )}
    </>
  );
}
