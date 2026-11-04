import { Activity } from "lucide-react";
import Link from "next/link";

import { cn } from "@/lib/cn";
import { EVENT_LABELS } from "@/features/applications/format";
import type { EventKind, RecentActivity } from "@/types/applications";

import { DashCard } from "./dash-card";
import { formatRelative } from "./time";

const PILULES: Record<EventKind, string> = {
  status_change: "bg-accent-soft text-on-accent-soft",
  note: "bg-success-soft text-on-success-soft",
  interview: "bg-highlight text-on-highlight",
  follow_up: "bg-warning-soft text-on-warning-soft",
  other: "bg-surface text-foreground-muted",
};

export interface ActivityCardProps {
  activities: readonly RecentActivity[];
  now?: Date;
}

/** Derniers événements de suivi, du plus récent au plus ancien. */
export function ActivityCard({ activities, now = new Date() }: ActivityCardProps) {
  return (
    <DashCard
      title="Activité récente"
      icon={Activity}
      moreHref="/applications"
      moreLabel="Ouvrir les candidatures"
    >
      {activities.length === 0 ? (
        <p className="mt-6 text-sm text-foreground-muted">
          Aucune activité : elle apparaît dès qu&apos;une candidature est suivie.
        </p>
      ) : (
        <ul className="mt-5 flex flex-col divide-y divide-border" aria-label="Dernières activités">
          {activities.slice(0, 4).map((a, i) => (
            <li
              key={`${a.application_id}-${a.occurred_at}-${i}`}
              className="flex flex-col gap-2 py-4"
            >
              <div className="flex items-center justify-between gap-3">
                <span className={cn("rounded-full px-3 py-1 text-sm font-medium", PILULES[a.kind])}>
                  {EVENT_LABELS[a.kind]}
                </span>
                <span className="text-sm text-foreground-muted">
                  {formatRelative(a.occurred_at, now)}
                </span>
              </div>
              <Link
                href={`/applications/${a.application_id}`}
                className="text-base font-medium text-foreground underline-offset-4 hover:underline"
              >
                {a.job_title}
              </Link>
              {a.body ? <p className="text-sm text-foreground-muted">{a.body}</p> : null}
              {a.company_name ? (
                <p>
                  <span className="rounded-full bg-surface px-3 py-1 text-sm text-foreground-muted">
                    {a.company_name}
                  </span>
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </DashCard>
  );
}
