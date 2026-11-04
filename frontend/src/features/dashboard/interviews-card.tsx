"use client";

import { ChevronLeft, ChevronRight, Video } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { IconButton } from "@/components/ui/icon-button";
import { cn } from "@/lib/cn";
import type { InterviewEvent } from "@/types/applications";

import { DashCard } from "./dash-card";
import { isSameDay, startOfDay, weekDays } from "./week";
import { formatDateParts } from "@/lib/regional";

const BARRES = ["bg-chart-2", "bg-chart-1", "bg-chart-3", "bg-chart-4"] as const;

// Formateurs construits à l'appel : langue, pays et fuseau suivent les préférences.
const jourCourt = { format: (d: Date) => formatDateParts(d, { weekday: "narrow" }) };
const jourLong = {
  format: (d: Date) => formatDateParts(d, { weekday: "long", day: "numeric", month: "long" }),
};
const heure = { format: (d: Date) => formatDateParts(d, { hour: "2-digit", minute: "2-digit" }) };

export interface InterviewsCardProps {
  interviews: readonly InterviewEvent[];
  /** Instant de référence (injecté pour les tests). */
  now?: Date;
}

/** Agenda de la semaine : entretiens réellement enregistrés dans les candidatures. */
export function InterviewsCard({ interviews, now = new Date() }: InterviewsCardProps) {
  const [decalage, setDecalage] = useState(0);
  const [choisi, setChoisi] = useState<Date>(startOfDay(now));
  const jours = useMemo(() => weekDays(now, decalage), [now, decalage]);
  const jourActif = jours.find((j) => isSameDay(j, choisi)) ?? jours[0] ?? choisi;

  const parJour = (jour: Date) =>
    interviews.filter((e) => isSameDay(new Date(e.occurred_at), jour));
  const duJour = parJour(jourActif);

  return (
    <DashCard title="Entretiens à venir" icon={Video} className="flex flex-col xl:p-7">
      <div className="mt-5 flex items-center gap-2">
        <IconButton
          size="sm"
          aria-label="Semaine précédente"
          onClick={() => setDecalage((d) => d - 1)}
        >
          <ChevronLeft className="size-4" aria-hidden="true" />
        </IconButton>
        <ul className="grid flex-1 grid-cols-7 gap-1" aria-label="Jours de la semaine">
          {jours.map((jour) => {
            const nombre = parJour(jour).length;
            const actif = isSameDay(jour, jourActif);
            return (
              <li key={jour.toISOString()}>
                <button
                  type="button"
                  aria-pressed={actif}
                  // Le nom commence par le texte visible (« L 2 ») : exigence WCAG 2.5.3.
                  aria-label={`${jourCourt.format(jour).toUpperCase()} ${jour.getDate()}, ${jourLong.format(jour)}${nombre ? ` : ${nombre} entretien${nombre > 1 ? "s" : ""}` : ""}`}
                  onClick={() => setChoisi(jour)}
                  className={cn(
                    "flex w-full flex-col items-center gap-1 rounded-2xl px-1 py-3 text-base",
                    actif
                      ? "bg-highlight font-semibold text-on-highlight"
                      : "text-foreground hover:bg-background-secondary",
                  )}
                >
                  {/* Un seul nœud de texte « M 3 » : il est repris tel quel dans le nom accessible. */}
                  <span aria-hidden="true" className="whitespace-pre-line text-center uppercase">
                    {`${jourCourt.format(jour)}\n${jour.getDate()}`}
                  </span>
                  <span
                    aria-hidden="true"
                    className={cn(
                      "size-1.5 rounded-full",
                      nombre > 0 ? (actif ? "bg-on-highlight" : "bg-accent") : "bg-transparent",
                    )}
                  />
                </button>
              </li>
            );
          })}
        </ul>
        <IconButton
          size="sm"
          aria-label="Semaine suivante"
          onClick={() => setDecalage((d) => d + 1)}
        >
          <ChevronRight className="size-4" aria-hidden="true" />
        </IconButton>
      </div>

      <div className="-mx-6 mt-5 border-t border-border xl:-mx-7" />

      {duJour.length > 0 ? (
        <ul className="mt-5 flex flex-col divide-y divide-border" aria-label="Entretiens du jour">
          {duJour.map((e, i) => (
            <li key={`${e.application_id}-${e.occurred_at}`} className="relative flex gap-4 py-4">
              <span
                aria-hidden="true"
                className={cn("w-1 shrink-0 rounded-full", BARRES[i % BARRES.length])}
              />
              <div className="min-w-0 flex-1">
                <Link
                  href={`/applications/${e.application_id}`}
                  className="flex items-center gap-2 font-medium text-foreground after:absolute after:inset-0"
                >
                  <Video className="size-5 shrink-0 text-foreground-muted" aria-hidden="true" />
                  <span className="truncate">
                    {e.job_title}
                    {e.company_name ? ` — ${e.company_name}` : ""}
                  </span>
                </Link>
                <p className="mt-1 text-sm text-foreground-muted">
                  {heure.format(new Date(e.occurred_at))}
                  {e.description ? ` · ${e.description}` : ""}
                </p>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-6 text-sm text-foreground-muted">
          {interviews.length === 0
            ? "Aucun entretien enregistré. Ajoutez-en depuis la fiche d'une candidature."
            : "Aucun entretien ce jour-là."}
        </p>
      )}
    </DashCard>
  );
}
