"use client";

import { useTaskEstimate } from "./use-ai";

/**
 * Coût maximal d'une opération IA, affiché avant de la lancer (TASK-010-28). Dit aussi quand
 * l'opération serait refusée aujourd'hui, et pourquoi : jamais de surprise après le clic.
 */
export function TaskCostNote({ task, enabled = true }: { task: string; enabled?: boolean }) {
  const estimation = useTaskEstimate(task, enabled);
  if (!enabled) return null;
  if (estimation.isPending) return null;
  if (estimation.isError) {
    return (
      <p className="text-xs text-foreground-muted">
        Coût estimé indisponible (l&apos;opération expliquera pourquoi si elle ne peut pas
        s&apos;exécuter).
      </p>
    );
  }
  const e = estimation.data;
  return (
    <p role="note" className="text-xs text-foreground-muted">
      {e.paid
        ? `Coût maximal estimé : ${e.cost} ${e.currency} (${e.provider}).`
        : `Gratuit : exécuté en local (${e.provider}).`}{" "}
      {e.allowed ? null : (
        <strong className="text-foreground">Refusé aujourd&apos;hui : {e.reason}</strong>
      )}
    </p>
  );
}
