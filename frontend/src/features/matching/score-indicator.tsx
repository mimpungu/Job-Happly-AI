import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/cn";
import type { Reliability } from "@/types/matching";

import { BAND_LABELS, RELIABILITY_LABELS, bandOf, type Band } from "./labels";

const BAR_CLASSES: Record<Band, string> = {
  good: "bg-success",
  fair: "bg-warning",
  low: "bg-foreground-subtle",
};

export interface ScoreIndicatorProps {
  /** Score 0-100 (nombre ou chaîne décimale de l'API) ; `null` = pas évalué. */
  score: string | number | null;
  reliability?: Reliability | null;
  size?: "compact" | "large";
}

/**
 * Compatibilité d'une offre. L'information passe toujours par du texte (note, tranche,
 * fiabilité), jamais par la seule couleur ; le score reste présenté comme indicatif.
 */
export function ScoreIndicator({
  score,
  reliability = null,
  size = "compact",
}: ScoreIndicatorProps) {
  if (score === null) {
    return (
      <Badge title="Aucun score calculé pour cette offre : calculez les scores depuis la recherche.">
        Non évalué
      </Badge>
    );
  }
  const note = Math.round(Number(score));
  const tranche = bandOf(note);
  const fiabilite = reliability ? RELIABILITY_LABELS[reliability] : null;
  const grand = size === "large";

  return (
    <div className={cn("flex flex-col gap-1", grand ? "min-w-48" : "min-w-28")}>
      <div className="flex items-baseline gap-2">
        <span className={cn("font-semibold text-foreground", grand ? "text-3xl" : "text-sm")}>
          {note}
          <span
            className={cn("font-normal text-foreground-muted", grand ? "text-base" : "text-xs")}
          >
            /100
          </span>
        </span>
        {grand ? <span className="text-sm text-foreground">{BAND_LABELS[tranche]}</span> : null}
      </div>
      <div
        role="meter"
        aria-label="Compatibilité"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={note}
        aria-valuetext={`${note} sur 100, ${BAND_LABELS[tranche].toLowerCase()}${fiabilite ? `, ${fiabilite.toLowerCase()}` : ""}`}
        className={cn(
          "w-full overflow-hidden rounded-full bg-surface-elevated",
          grand ? "h-2" : "h-1.5",
        )}
      >
        <div
          className={cn("h-full rounded-full", BAR_CLASSES[tranche])}
          style={{ width: `${note}%` }}
        />
      </div>
      {fiabilite && (grand || reliability !== "high") ? (
        <span className="text-xs text-foreground-muted">{fiabilite}</span>
      ) : null}
    </div>
  );
}
