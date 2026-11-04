import type { EventKind } from "@/types/applications";

const ABSENT = "Non renseignée";

/** Date et heure au fuseau du navigateur ; une date absente n'est jamais remplacée par une valeur. */
export function formatDateTime(iso: string | null): string {
  if (!iso) return ABSENT;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return ABSENT;
  return new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export function formatDay(iso: string | null): string {
  if (!iso) return ABSENT;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return ABSENT;
  return new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium" }).format(date);
}

/** Pourcentage ; `null` = aucune donnée, affiché comme tel et jamais comme 0 %. */
export function formatPercent(valeur: number | null): string {
  if (valeur === null) return "—";
  return `${new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 }).format(valeur)} %`;
}

/** Valeur d'un `<input type="datetime-local">` (heure locale) → instant ISO avec fuseau. */
export function localInputToIso(valeur: string): string | undefined {
  if (!valeur) return undefined;
  const date = new Date(valeur);
  return Number.isNaN(date.getTime()) ? undefined : date.toISOString();
}

/** Instant → valeur d'un `<input type="datetime-local">` (heure locale, à la minute). */
export function isoToLocalInput(date: Date): string {
  const decale = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return decale.toISOString().slice(0, 16);
}

export const EVENT_LABELS: Record<EventKind, string> = {
  status_change: "Statut",
  note: "Note",
  interview: "Entretien",
  follow_up: "Relance",
  other: "Autre",
};

/** Une relance est échue quand sa date est atteinte ; la comparaison se fait côté affichage. */
export function isOverdue(iso: string | null, maintenant: Date = new Date()): boolean {
  if (!iso) return false;
  const date = new Date(iso);
  return !Number.isNaN(date.getTime()) && date.getTime() <= maintenant.getTime();
}
