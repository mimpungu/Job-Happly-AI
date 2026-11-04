import { Target } from "lucide-react";
import Link from "next/link";
import { useId } from "react";

import { buttonVariants } from "@/components/ui/button";
import type { TopMatch } from "@/types/applications";

import { Monogram } from "./monogram";

const formatScore = (score: number) =>
  new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 }).format(score);

export interface TopMatchesCardProps {
  matches: readonly TopMatch[];
  /** `null` tant qu'aucun score n'existe : l'absence de score n'est pas une liste vide. */
  scoredOffers: number | null;
}

/** Les trois offres les plus compatibles avec le profil validé (scores réels du moteur). */
export function TopMatchesCard({ matches, scoredOffers }: TopMatchesCardProps) {
  const id = useId();
  return (
    <section aria-labelledby={id} className="rounded-xl border border-border bg-shell p-6 xl:p-7">
      <span className="inline-flex items-center gap-2 rounded-full bg-accent-soft px-4 py-2 text-sm font-medium text-on-accent-soft">
        <Target className="size-4" aria-hidden="true" />
        Correspondances
      </span>
      <h2 id={id} className="mt-5 text-2xl font-semibold text-foreground xl:text-3xl">
        Top 3 des offres les plus compatibles
      </h2>

      {matches.length > 0 ? (
        <ol className="mt-6 flex flex-col gap-3" aria-label="Offres les plus compatibles">
          {matches.map((m, i) => (
            <li
              key={m.offer_id}
              className="relative flex items-center gap-4 rounded-full bg-surface py-3 pl-3 pr-4"
            >
              <Monogram name={m.company_name ?? m.title} />
              <div className="min-w-0 flex-1">
                <Link
                  href={`/jobs/${m.offer_id}`}
                  className="block truncate font-medium text-foreground after:absolute after:inset-0 after:rounded-full"
                >
                  {m.title}
                </Link>
                <p className="truncate text-sm text-foreground-muted">
                  {m.company_name ?? "Entreprise inconnue"}
                </p>
              </div>
              <p className="text-2xl font-semibold text-foreground">
                {formatScore(m.score)}
                <span className="text-sm font-normal text-foreground-muted">
                  <span aria-hidden="true">/100</span>
                  <span className="sr-only"> sur 100</span>
                </span>
              </p>
              <span
                aria-label={`Rang ${i + 1}`}
                className="flex size-8 shrink-0 items-center justify-center rounded-full bg-background-secondary text-sm text-foreground-muted"
              >
                {i + 1}
              </span>
            </li>
          ))}
        </ol>
      ) : (
        <div className="mt-6 flex flex-col items-start gap-4 rounded-xl bg-background-secondary p-5">
          <p className="text-sm text-foreground-muted">
            {scoredOffers === null
              ? "Aucun score n'est encore calculé. Validez votre profil dans l'Espace CV, puis calculez les scores depuis la recherche."
              : "Aucune offre à proposer : toutes les offres notées sont déjà suivies ou ignorées."}
          </p>
          <Link
            href={scoredOffers === null ? "/cv-studio" : "/jobs"}
            className={buttonVariants({ variant: "secondary" })}
          >
            {scoredOffers === null ? "Valider mon profil" : "Chercher des offres"}
          </Link>
        </div>
      )}
    </section>
  );
}
