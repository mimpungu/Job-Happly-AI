"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { formatDateParts, formatNumber } from "@/lib/regional";
import type { AIDailySpend } from "@/types/ai";

const HAUTEUR = 160;
const EPAISSEUR_MAX = 24;

const montant = (valeur: number, devise: string) =>
  `${formatNumber(valeur, { maximumFractionDigits: 4 })} ${devise}`;

const jourCourt = (iso: string) =>
  formatDateParts(new Date(`${iso}T00:00:00Z`), {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });

/** Graduations rondes (0, 1/2 et le maximum) pour que l'axe se lise sans calcul. */
function maximumRond(valeur: number): number {
  if (valeur <= 0) return 1;
  const exposant = 10 ** Math.floor(Math.log10(valeur));
  const mantisse = valeur / exposant;
  const arrondie = mantisse <= 1 ? 1 : mantisse <= 2 ? 2 : mantisse <= 5 ? 5 : 10;
  return arrondie * exposant;
}

export interface SpendChartProps {
  days: readonly AIDailySpend[];
  currency: string;
  /** Plafond journalier (trait de référence) ; `null` s'il n'est pas défini. */
  dailyBudget: string | null;
}

/**
 * Dépense par jour du mois en cours. Une barre fine par jour (jours sans dépense inclus, à zéro),
 * le plafond journalier en trait de référence, une info-bulle par barre et une vue en tableau
 * pour qui ne lit pas un graphique.
 */
export function SpendChart({ days, currency, dailyBudget }: SpendChartProps) {
  const [survol, setSurvol] = useState<number | null>(null);
  const [tableau, setTableau] = useState(false);
  const valeurs = days.map((j) => Number(j.cost));
  const plafond = dailyBudget === null ? null : Number(dailyBudget);
  const max = maximumRond(Math.max(0, ...valeurs, plafond ?? 0));
  const total = valeurs.reduce((a, b) => a + b, 0);
  const resume = `Dépense du mois par jour : ${montant(total, currency)} au total sur ${days.length} jour${days.length > 1 ? "s" : ""}.`;

  if (days.length === 0) return null;
  const hauteurDe = (v: number) => (v > 0 ? Math.max(2, (v / max) * HAUTEUR) : 0);

  return (
    <figure className="flex flex-col gap-2">
      <figcaption className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <span className="text-foreground-muted">Dépense par jour, ce mois-ci</span>
        <Button variant="ghost" size="sm" onClick={() => setTableau((v) => !v)}>
          {tableau ? "Afficher le graphique" : "Afficher en tableau"}
        </Button>
      </figcaption>

      {tableau ? (
        <div
          className="max-h-64 overflow-auto"
          tabIndex={0}
          role="region"
          aria-label="Dépense par jour (tableau)"
        >
          <table className="w-full text-left text-sm">
            <thead className="text-foreground-muted">
              <tr>
                <th scope="col" className="py-1 pr-3">
                  Jour
                </th>
                <th scope="col" className="py-1 text-right">
                  Dépense
                </th>
              </tr>
            </thead>
            <tbody>
              {days.map((j) => (
                <tr key={j.date} className="border-t border-border">
                  <td className="py-1 pr-3">{jourCourt(j.date)}</td>
                  <td className="py-1 text-right">{montant(Number(j.cost), currency)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="flex gap-2" role="img" aria-label={resume}>
          {/* Axe vertical : 0, moitié, maximum, en texte discret. */}
          <div
            className="flex flex-col justify-between text-right text-xs text-foreground-muted"
            style={{ height: HAUTEUR }}
            aria-hidden="true"
          >
            <span>{formatNumber(max, { maximumFractionDigits: 4 })}</span>
            <span>{formatNumber(max / 2, { maximumFractionDigits: 4 })}</span>
            <span>0</span>
          </div>
          <div className="relative min-w-0 flex-1">
            <div
              className="relative flex items-end border-b border-border"
              style={{ height: HAUTEUR }}
              onMouseLeave={() => setSurvol(null)}
            >
              {[0, 0.5, 1].map((niveau) => (
                <div
                  key={niveau}
                  aria-hidden="true"
                  className="pointer-events-none absolute inset-x-0 border-t border-border/60"
                  style={{ bottom: `${niveau * 100}%` }}
                />
              ))}
              {plafond !== null ? (
                <div
                  aria-hidden="true"
                  className="pointer-events-none absolute inset-x-0 border-t-2 border-warning"
                  style={{ bottom: `${(plafond / max) * 100}%` }}
                >
                  <span className="absolute right-0 -top-5 rounded bg-surface px-1 text-xs text-foreground-muted">
                    Plafond journalier : {montant(plafond, currency)}
                  </span>
                </div>
              ) : null}
              {days.map((j, i) => (
                <div
                  key={j.date}
                  className="relative flex h-full flex-1 items-end justify-center px-px"
                  onMouseEnter={() => setSurvol(i)}
                >
                  {/* Cible de survol : toute la colonne, pas seulement la barre fine. */}
                  <div
                    className="w-full rounded-t-[4px] bg-chart-1"
                    style={{ height: hauteurDe(valeurs[i] ?? 0), maxWidth: EPAISSEUR_MAX }}
                    aria-hidden="true"
                  />
                  {survol === i ? (
                    <div
                      role="tooltip"
                      className="pointer-events-none absolute bottom-full z-10 mb-1 -translate-x-1/2 whitespace-nowrap rounded-md border border-border bg-surface-elevated px-2 py-1 text-xs text-foreground shadow-md"
                      style={{ left: "50%" }}
                    >
                      {jourCourt(j.date)} : {montant(valeurs[i] ?? 0, currency)}
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
            <div className="flex pt-1 text-xs text-foreground-muted" aria-hidden="true">
              {days.map((j, i) => (
                <span key={j.date} className="flex-1 text-center">
                  {i === 0 || i === days.length - 1 || (i + 1) % 5 === 0 ? i + 1 : ""}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
    </figure>
  );
}
