"use client";

import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Panel } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { DataSource } from "@/types/sources";

import { useDataSources } from "./use-sources";

const STATUTS: Record<DataSource["status"], { label: string; variant: BadgeProps["variant"] }> = {
  ok: { label: "Opérationnelle", variant: "success" },
  error: { label: "En erreur", variant: "danger" },
  unsupported: { label: "Non supportée", variant: "warning" },
  not_configured: { label: "Non configurée", variant: "warning" },
  never_checked: { label: "Jamais interrogée", variant: "neutral" },
};

const date = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" }) : "—";

/** État de chaque source : dernier accès, dernière erreur, offres et configuration requise. */
export function DataSourcesPanel() {
  const sources = useDataSources();
  return (
    <Panel title="Sources de données">
      {sources.isPending ? (
        <Skeleton className="h-16 w-full" role="status" aria-label="Chargement des sources" />
      ) : sources.isError ? (
        <p role="alert" className="text-sm">
          Impossible de lire les sources : {sources.error.message}
        </p>
      ) : (
        <ul className="flex flex-col divide-y divide-border text-sm">
          {sources.data.map((s) => (
            <li key={s.key} className="flex flex-col gap-1 py-3 first:pt-0 last:pb-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium text-foreground">{s.name}</span>
                <Badge variant={STATUTS[s.status].variant}>{STATUTS[s.status].label}</Badge>
              </div>
              <p className="text-foreground-muted">
                {s.countries.length > 0 ? `Pays : ${s.countries.join(", ")}` : "Tous pays"} ·{" "}
                {s.offer_count} offre{s.offer_count > 1 ? "s" : ""} · Dernier accès{" "}
                {date(s.last_checked_at)}
              </p>
              {s.requires_configuration && !s.configured ? (
                <p className="text-foreground-muted">
                  Identifiants requis : renseignez-les dans la configuration du serveur.
                </p>
              ) : null}
              {s.last_error ? (
                <p role="note" className="text-foreground-muted">
                  Dernière erreur : {s.last_error}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
