"use client";

import { formatDate } from "@/features/jobs/format";

import { describeChange } from "./draft";
import { useProfileHistory } from "./use-profile";

export function HistoryPanel() {
  const historique = useProfileHistory(true);

  if (historique.isPending) return <p className="text-sm text-foreground-muted">Chargement…</p>;
  if (historique.isError) {
    return (
      <p role="alert" className="text-sm text-danger">
        {historique.error.message}
      </p>
    );
  }
  if (historique.data.length === 0) {
    return <p className="text-sm text-foreground-muted">Aucune modification enregistrée.</p>;
  }
  return (
    <section aria-label="Historique des modifications" className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold text-foreground">Historique des modifications</h2>
      <ol className="flex flex-col divide-y divide-border rounded-lg border border-border">
        {historique.data.map((ligne) => (
          <li
            key={ligne.id}
            className="flex flex-wrap items-baseline justify-between gap-2 px-4 py-3 text-sm"
          >
            <span className="text-foreground">{describeChange(ligne)}</span>
            <span className="text-xs text-foreground-muted">
              Version {ligne.profile_version} · {formatDate(ligne.created_at)}
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}
