import { Compass, Search, Wallet } from "lucide-react";
import Link from "next/link";

import { formatDateTime } from "@/features/applications/format";
import type { AIBudget, RecentSearch } from "@/types/applications";

import { BudgetChart } from "./budget-chart";
import { DashCard } from "./dash-card";
import { formatMoney } from "./format";

const STATUTS_RECHERCHE: Record<string, string> = {
  running: "En cours",
  succeeded: "Réussie",
  partial: "Transférable",
  failed: "Échec",
};

export interface ExtrasRowProps {
  totalOffers: number;
  newOffers: number;
  relevantOffers: number | null;
  relevanceThreshold: number;
  budget: AIBudget;
  searches: readonly RecentSearch[];
}

/** Compléments du tableau de bord : offres à traiter, budget IA du mois, dernières recherches. */
export function ExtrasRow({
  totalOffers,
  newOffers,
  relevantOffers,
  relevanceThreshold,
  budget,
  searches,
}: ExtrasRowProps) {
  const depense = Number(budget.spent);
  const plafond = budget.limit === null ? null : Number(budget.limit);
  const part = plafond ? Math.min(100, Math.round((depense / plafond) * 100)) : null;

  return (
    <div className="grid gap-5 lg:grid-cols-3">
      <DashCard
        title="Offres à traiter"
        icon={Compass}
        moreHref="/jobs"
        moreLabel="Ouvrir la recherche"
      >
        <dl className="mt-5 grid grid-cols-2 gap-4">
          <div>
            <dt className="text-sm text-foreground-muted">Nouvelles offres</dt>
            <dd className="mt-1 text-3xl font-semibold text-foreground">{newOffers}</dd>
            <dd className="text-sm text-foreground-muted">Vues depuis 7 jours, non traitées</dd>
          </div>
          <div>
            <dt className="text-sm text-foreground-muted">Offres pertinentes</dt>
            <dd className="mt-1 text-3xl font-semibold text-foreground">
              {relevantOffers === null ? "—" : relevantOffers}
            </dd>
            <dd className="text-sm text-foreground-muted">
              {relevantOffers === null
                ? "Aucun score calculé : validez votre profil"
                : `Score d'au moins ${relevanceThreshold}`}
            </dd>
          </div>
        </dl>
        <p className="mt-4 text-sm text-foreground-muted">
          {totalOffers} offre{totalOffers > 1 ? "s" : ""} trouvée{totalOffers > 1 ? "s" : ""} au
          total.
        </p>
      </DashCard>

      <DashCard
        title="Budget IA du mois"
        icon={Wallet}
        moreHref="/ai-center"
        moreLabel="Ouvrir le Centre IA"
        className="flex flex-col"
      >
        <p className="mt-5 text-sm text-foreground">
          Dépensé : <strong>{formatMoney(budget.spent, budget.currency)}</strong>
          {budget.limit !== null ? ` sur ${formatMoney(budget.limit, budget.currency)}` : ""}
        </p>
        {part !== null ? (
          <div
            role="progressbar"
            aria-label="Part du plafond mensuel consommée"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={part}
            className="mt-3 h-2 overflow-hidden rounded-full bg-background-secondary"
          >
            <div className="h-full bg-accent" style={{ width: `${part}%` }} />
          </div>
        ) : (
          <p className="mt-3 text-sm text-foreground-muted">
            Aucun plafond mensuel défini : aucun appel payant n&apos;est possible tant qu&apos;il
            n&apos;existe pas.
          </p>
        )}
        <BudgetChart />
      </DashCard>

      <DashCard
        title="Dernières recherches"
        icon={Search}
        moreHref="/jobs"
        moreLabel="Ouvrir la recherche"
      >
        {searches.length === 0 ? (
          <p className="mt-5 text-sm text-foreground-muted">
            Aucune recherche lancée pour le moment.
          </p>
        ) : (
          <ul className="mt-5 flex flex-col gap-3" aria-label="Dernières recherches">
            {searches.map((s) => (
              <li key={s.id} className="text-sm">
                <p className="text-foreground">{s.label}</p>
                <p className="text-foreground-muted">
                  {formatDateTime(s.started_at)} · {STATUTS_RECHERCHE[s.status] ?? s.status}
                  {s.result_count !== null
                    ? ` · ${s.result_count} résultat${s.result_count > 1 ? "s" : ""}`
                    : ""}
                </p>
              </li>
            ))}
          </ul>
        )}
        <Link
          href="/saved-jobs"
          className="mt-4 inline-block text-sm text-accent underline underline-offset-4"
        >
          Offres sauvegardées
        </Link>
      </DashCard>
    </div>
  );
}
