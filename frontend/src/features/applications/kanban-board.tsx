import Link from "next/link";

import { StatusBadge, statusLabel } from "@/components/ui/status-badge";
import type { KanbanView } from "@/types/applications";

import { formatDay } from "./format";

/**
 * Colonnes par statut, réparties sur deux rangées qui défilent horizontalement ; la liste de
 * chaque colonne défile verticalement. Ainsi, beaucoup de statuts et de candidatures restent
 * lisibles sans une seule longue ligne.
 *
 * Colonnes par statut. Le changement de statut se fait depuis la fiche : il est validé par la
 * machine à états (et l'envoi se confirme), ce qu'un glisser-déposer ne saurait pas exprimer.
 */
export function KanbanBoard({ view }: { view: KanbanView }) {
  return (
    <div
      // Zone défilante : focalisable au clavier (sinon inaccessible sans souris).
      tabIndex={0}
      className="grid auto-cols-[16rem] grid-flow-col grid-rows-2 gap-4 overflow-x-auto pb-2"
      role="group"
      aria-label="Kanban des candidatures"
    >
      {view.columns.map((colonne) => (
        <section
          key={colonne.status}
          aria-label={`${statusLabel(colonne.status)} : ${colonne.count}`}
          className="flex min-h-0 flex-col gap-2 rounded-lg border border-border bg-background-secondary p-3"
        >
          <header className="flex items-center justify-between gap-2">
            <StatusBadge status={colonne.status} />
            <span className="text-sm text-foreground-muted">{colonne.count}</span>
          </header>
          {colonne.count === 0 ? (
            <p className="py-4 text-center text-xs text-foreground-muted">Aucune candidature</p>
          ) : (
            <ul
              tabIndex={0}
              aria-label={`Candidatures : ${statusLabel(colonne.status)}`}
              className="flex max-h-72 flex-col gap-2 overflow-y-auto pr-1"
            >
              {colonne.items.map((c) => (
                <li key={c.id} className="rounded-md border border-border bg-surface p-3">
                  <Link
                    href={`/applications/${c.id}`}
                    className="text-sm font-medium text-foreground underline-offset-4 hover:underline"
                  >
                    {c.offer?.title ?? "Offre introuvable"}
                  </Link>
                  <p className="text-xs text-foreground-muted">
                    {c.offer?.company_name ?? "Entreprise inconnue"}
                  </p>
                  <p className="mt-1 text-xs text-foreground-muted">
                    Mise à jour le {formatDay(c.updated_at)}
                  </p>
                </li>
              ))}
            </ul>
          )}
          {colonne.has_more ? (
            <Link
              href={`/applications?status=${colonne.status}`}
              className="text-xs text-accent underline-offset-4 hover:underline"
            >
              {colonne.count - colonne.items.length} autre
              {colonne.count - colonne.items.length > 1 ? "s" : ""} : voir dans le tableau
            </Link>
          ) : null}
        </section>
      ))}
    </div>
  );
}
