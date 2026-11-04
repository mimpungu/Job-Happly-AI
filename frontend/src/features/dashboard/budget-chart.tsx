"use client";

import { SpendChart } from "@/features/ai/spend-chart";
import { useAIUsage } from "@/features/ai/use-ai";

/**
 * Dépense IA par jour, sous la jauge du mois. Données du Centre IA : une panne de ce service
 * n'enlève rien d'autre à la carte (la jauge vient du tableau de bord), on n'affiche donc ni
 * chargement ni erreur, seulement le graphique quand il est disponible.
 *
 * La hauteur de la carte ne dépend pas du graphique : il occupe l'espace libre sous la jauge (la
 * grille étire déjà les trois cartes à la même hauteur) et est posé en absolu, donc il ne
 * contribue pas à la hauteur naturelle de la carte. `min-h-16` garantit un graphique lisible
 * quand la carte est seule dans sa rangée (écran étroit).
 */
export function BudgetChart() {
  const usage = useAIUsage();
  const jours = usage.data?.daily_spend;
  if (!Array.isArray(jours) || jours.length === 0) return null;
  return (
    <div className="relative mt-4 min-h-16 flex-1">
      <div className="absolute inset-0">
        <SpendChart
          days={jours}
          currency={usage.data?.currency ?? ""}
          dailyBudget={usage.data?.daily_budget ?? null}
          compact
        />
      </div>
    </div>
  );
}
