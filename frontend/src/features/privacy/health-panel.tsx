"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { ComponentHealth, HealthStatus } from "@/types/privacy";

import { useHealth, useMetrics } from "./use-privacy";

const STATUS_LABELS: Record<HealthStatus, string> = {
  ok: "Opérationnel",
  degraded: "Dégradé",
  down: "En panne",
  not_configured: "Non configuré",
};
const STATUS_VARIANTS: Record<HealthStatus, "success" | "warning" | "danger" | "neutral"> = {
  ok: "success",
  degraded: "warning",
  down: "danger",
  not_configured: "neutral",
};
const NAMES: Record<string, string> = {
  database: "Base de données",
  storage: "Stockage des documents",
  latex: "Compilation LaTeX",
  ai: "Intelligence artificielle",
  sources: "Sources d'offres",
  tasks: "Tâches planifiées et de fond",
};

function Component({ c }: { c: ComponentHealth }) {
  return (
    <li className="flex flex-wrap items-start justify-between gap-2 py-3 text-sm">
      <div className="flex flex-col gap-1">
        <span className="font-medium">{NAMES[c.name] ?? c.name}</span>
        {c.detail ? <span className="text-foreground-muted">{c.detail}</span> : null}
      </div>
      <Badge variant={STATUS_VARIANTS[c.status]}>{STATUS_LABELS[c.status]}</Badge>
    </li>
  );
}

function duree(secondes: number): string {
  if (secondes < 120) return `${secondes} s`;
  if (secondes < 7200) return `${Math.round(secondes / 60)} min`;
  return `${Math.round(secondes / 3600)} h`;
}

/** Tableau de santé : composants, tâches et performances mesurées depuis le démarrage. */
export function HealthPanel() {
  const sante = useHealth();
  const mesures = useMetrics();

  return (
    <Panel
      title="Santé de l'application"
      actions={
        <Button
          variant="secondary"
          size="sm"
          onClick={() => {
            void sante.refetch();
            void mesures.refetch();
          }}
        >
          Actualiser
        </Button>
      }
    >
      {sante.isPending ? (
        <Skeleton className="h-40 w-full" role="status" aria-label="Chargement" />
      ) : sante.isError ? (
        <p role="alert" className="text-sm">
          Impossible de lire l&apos;état de santé : {sante.error.message}
        </p>
      ) : (
        <div className="flex flex-col gap-4">
          <p className="flex items-center gap-2 text-sm">
            État général :
            <Badge variant={STATUS_VARIANTS[sante.data.status]}>
              {STATUS_LABELS[sante.data.status]}
            </Badge>
          </p>
          <ul className="flex flex-col divide-y divide-border">
            {sante.data.components.map((c) => (
              <Component key={c.name} c={c} />
            ))}
          </ul>
        </div>
      )}
      {mesures.data ? (
        <div className="mt-4 flex flex-col gap-2 border-t border-border pt-4 text-sm">
          <p className="text-foreground-muted">
            Depuis le démarrage ({duree(mesures.data.uptime_seconds)}) : {mesures.data.requests}{" "}
            requête(s), {mesures.data.server_errors} erreur(s) serveur, {mesures.data.rate_limited}{" "}
            refus pour excès de débit. Mesures conservées en mémoire : elles repartent à zéro au
            redémarrage.
          </p>
          <details>
            <summary className="cursor-pointer font-medium">Durées par route</summary>
            <table className="mt-2 w-full text-left text-xs">
              <caption className="sr-only">Durées de réponse par route</caption>
              <thead>
                <tr>
                  <th scope="col">Route</th>
                  <th scope="col">Appels</th>
                  <th scope="col">Moyenne</th>
                  <th scope="col">p95</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(mesures.data.routes)
                  .sort(([, a], [, b]) => b.p95_ms - a.p95_ms)
                  .slice(0, 10)
                  .map(([route, m]) => (
                    <tr key={route}>
                      <th scope="row" className="font-normal">
                        {route}
                      </th>
                      <td>{m.count}</td>
                      <td>{m.avg_ms} ms</td>
                      <td>{m.p95_ms} ms</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </details>
        </div>
      ) : null}
    </Panel>
  );
}
