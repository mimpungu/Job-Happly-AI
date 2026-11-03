import { Badge } from "@/components/ui/badge";
import { Panel } from "@/components/ui/card";
import type { CriterionResult } from "@/types/matching";

import { CRITERION_LABELS, bandOf } from "./labels";
import { cn } from "@/lib/cn";

/** Détail critère par critère : poids, note ou « données manquantes », et explication. */
export function CriteriaBreakdown({ criteria }: { criteria: readonly CriterionResult[] }) {
  const poidsTotal = criteria.reduce((somme, c) => somme + Number(c.weight), 0);
  return (
    <Panel title="Détail par critère">
      <ul className="flex flex-col divide-y divide-border">
        {criteria.map((c) => {
          const part = poidsTotal > 0 ? Math.round((Number(c.weight) / poidsTotal) * 100) : 0;
          const note = c.score === null ? null : Math.round(Number(c.score) * 100);
          return (
            <li key={c.criterion} className="flex flex-col gap-2 py-3 first:pt-0 last:pb-0">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-sm font-medium text-foreground">
                  {CRITERION_LABELS[c.criterion]}
                </h3>
                <div className="flex items-center gap-2 text-xs text-foreground-muted">
                  <span>Poids {part} %</span>
                  {c.uncertain ? <Badge variant="warning">À vérifier</Badge> : null}
                  {note === null ? (
                    <Badge>Données manquantes — non compté</Badge>
                  ) : (
                    <span className="font-medium text-foreground">{note} %</span>
                  )}
                </div>
              </div>
              {note !== null ? (
                <div
                  role="meter"
                  aria-label={`${CRITERION_LABELS[c.criterion]} : ${note} %`}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={note}
                  className="h-1.5 w-full overflow-hidden rounded-full bg-surface-elevated"
                >
                  <div
                    className={cn(
                      "h-full rounded-full",
                      bandOf(note) === "good"
                        ? "bg-success"
                        : bandOf(note) === "fair"
                          ? "bg-warning"
                          : "bg-foreground-subtle",
                    )}
                    style={{ width: `${note}%` }}
                  />
                </div>
              ) : null}
              <p className="text-sm text-foreground-muted">{c.explanation}</p>
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}
