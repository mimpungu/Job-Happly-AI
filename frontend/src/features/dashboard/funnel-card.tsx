"use client";

import { ChartColumn, Lightbulb } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import type { Funnel } from "@/types/applications";

import { DashCard } from "./dash-card";
import { biggestDrop, funnelStages, niceTicks, type FunnelStage } from "./funnel";
import { formatNumber } from "@/lib/regional";

const nombre = (n: number) => formatNumber(n);

// Dégradé et hachures : dérogation à l'interdiction des dégradés validée par le propriétaire
// pour ce graphique (ADR-0017). Les couleurs viennent des jetons, donc des deux thèmes.
const HACHURES =
  "repeating-linear-gradient(135deg, var(--color-chart-hatch-line) 0 1px, var(--color-chart-hatch-fill) 1px 9px)";
const DEGRADE =
  "linear-gradient(180deg, var(--color-chart-active-start), var(--color-chart-active-end))";

/** Position (en % de la hauteur du tracé) du sommet d'une étape. */
const hauteur = (valeur: number, maximum: number) => (maximum > 0 ? (valeur / maximum) * 100 : 0);

function tooltipText(etape: FunnelStage): string {
  const base = `${nombre(etape.value)} ${etape.label.toLowerCase()}`;
  if (etape.conversion === null || etape.dropOff === null) return base;
  return `${base} | Conversion : ${etape.conversion} % | Perte : −${etape.dropOff} %`;
}

function Insight({ stages }: { stages: readonly FunnelStage[] }) {
  const pire = biggestDrop(stages);
  const donnees = stages.some((s) => s.previous !== null && (s.previous ?? 0) > 0);
  return (
    <div className="mt-6 flex flex-col gap-4 rounded-xl bg-accent-soft p-5 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-start gap-3">
        <Lightbulb className="mt-0.5 size-5 shrink-0 text-on-accent-soft" aria-hidden="true" />
        <div>
          <p className="text-sm text-on-accent-soft">Où votre recherche perd-elle le plus ?</p>
          <p className="text-base font-medium text-foreground">
            {pire && pire.previous !== null
              ? `Le plus gros écart : de « ${stages[stages.indexOf(pire) - 1]?.label ?? ""} » à « ${pire.label} » (${nombre(pire.value)} sur ${nombre(pire.previous)}, ${pire.conversion ?? 0} % conservés).`
              : donnees
                ? "Aucune perte entre les étapes : chaque étape conserve tout ce qui la précède."
                : "Pas encore assez de données : suivez vos premières offres pour voir apparaître l'entonnoir."}
          </p>
        </div>
      </div>
      <Link
        href={pire?.href ?? "/jobs"}
        className={cn(buttonVariants({ variant: "primary", size: "lg" }), "shrink-0 rounded-full")}
      >
        {pire?.action ?? "Chercher des offres"}
      </Link>
    </div>
  );
}

/** Entonnoir Offres → Suivies → Envoyées → Réponses → Offres reçues, chiffres réels. */
export function FunnelCard({ funnel }: { funnel: Funnel }) {
  const stages = funnelStages(funnel);
  const ticks = niceTicks(Math.max(...stages.map((s) => s.value)));
  const maximum = ticks[ticks.length - 1] ?? 1;
  const vide = stages.every((s) => s.value === 0);
  // La deuxième étape est mise en avant par défaut, comme dans la maquette.
  const [actif, setActif] = useState(1);
  const colonne = 100 / stages.length;

  return (
    <DashCard
      title="Progression de la recherche"
      icon={ChartColumn}
      moreHref="/applications"
      moreLabel="Ouvrir les candidatures"
      className="xl:p-7"
    >
      <div className="mt-6 grid grid-cols-[3rem_1fr] gap-x-3">
        <div />
        <div className="grid grid-cols-5">
          {stages.map((s) => (
            <div key={s.key} className="border-l border-border px-4 first:border-l-0">
              <p className="text-sm text-foreground-muted">{s.label}</p>
              <p className="text-3xl font-semibold text-foreground">{nombre(s.value)}</p>
            </div>
          ))}
        </div>

        <div className="relative h-64" aria-hidden="true">
          {ticks.map((t) => (
            <span
              key={t}
              className="absolute left-0 -translate-y-1/2 text-sm text-foreground-muted"
              style={{ bottom: `${hauteur(t, maximum)}%` }}
            >
              {nombre(t)}
            </span>
          ))}
        </div>

        <div className="relative h-64">
          {vide ? (
            <p className="absolute inset-x-0 bottom-4 text-center text-sm text-foreground-muted">
              Aucune donnée : l&apos;entonnoir se dessine dès les premières offres.
            </p>
          ) : (
            <>
              {/* Le dessin est décoratif : chiffres et conversions sont lus dans le texte et les boutons. */}
              <div aria-hidden="true" className="absolute inset-0">
                {stages.map((s, i) => {
                  const h = hauteur(s.value, maximum);
                  const suivante = stages[i + 1];
                  // Le flanc rejoint le sommet de l'étape suivante : même pente que la maquette.
                  const pente = suivante && s.value > 0 ? (1 - suivante.value / s.value) * 100 : 0;
                  return (
                    <div key={s.key}>
                      <div
                        className="absolute bottom-0"
                        style={{
                          left: `${i * colonne}%`,
                          width: `${colonne}%`,
                          height: `${h}%`,
                          background: i === actif ? DEGRADE : HACHURES,
                          clipPath: `polygon(0 0, 78% 0, 100% ${pente}%, 100% 100%, 0 100%)`,
                        }}
                      />
                      <span
                        className="absolute h-1.5 w-10 rounded-full bg-accent"
                        style={{
                          left: `${i * colonne + colonne / 4}%`,
                          bottom: `calc(${h}% + 0.75rem)`,
                        }}
                      />
                    </div>
                  );
                })}
                <p
                  className="pointer-events-none absolute z-10 w-max rounded-2xl border border-border bg-surface-elevated px-4 py-2 text-sm text-foreground shadow-md"
                  style={{
                    // Ne dépasse jamais du graphique : sur petit écran, le texte passe à la ligne.
                    maxWidth: `${100 - Math.min(actif * colonne, 100 - 2 * colonne)}%`,
                    left: `${Math.min(actif * colonne, 100 - 2 * colonne)}%`,
                    bottom: `calc(${hauteur(stages[actif]?.value ?? 0, maximum)}% + 2.25rem)`,
                  }}
                >
                  {tooltipText(stages[actif] as FunnelStage)}
                </p>
              </div>
              {/* Colonnes interactives : survol ou focus clavier pour lire conversion et perte. */}
              {stages.map((s, i) => (
                <button
                  key={s.key}
                  type="button"
                  aria-label={tooltipText(s)}
                  aria-pressed={i === actif}
                  onMouseEnter={() => setActif(i)}
                  onFocus={() => setActif(i)}
                  className="absolute inset-y-0 rounded-md"
                  style={{ left: `${i * colonne}%`, width: `${colonne}%` }}
                />
              ))}
            </>
          )}
        </div>
      </div>

      <Insight stages={stages} />
    </DashCard>
  );
}
