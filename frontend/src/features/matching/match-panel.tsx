"use client";

import { ServerCrash, UserRoundCheck } from "lucide-react";
import Link from "next/link";

import { buttonVariants, Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Panel } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate } from "@/features/jobs/format";
import { ApiError } from "@/services/api-client";

import { CriteriaBreakdown } from "./criteria-breakdown";
import { ScoreIndicator } from "./score-indicator";
import { SkillMatchPanel } from "./skill-match-panel";
import { useOfferMatch } from "./use-matching";

/** Compatibilité d'une offre avec le profil validé : score, raisons, compétences, détail. */
export function MatchPanel({ offerId }: { offerId: string }) {
  const match = useOfferMatch(offerId);

  if (match.isPending) {
    return (
      <div role="status" aria-label="Calcul de la compatibilité" className="flex flex-col gap-3">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }
  if (match.isError) {
    const sansProfil =
      match.error instanceof ApiError && match.error.code === "no_validated_profile";
    return (
      <EmptyState
        icon={sansProfil ? UserRoundCheck : ServerCrash}
        title={
          sansProfil ? "Compatibilité indisponible" : "Impossible de calculer la compatibilité"
        }
        description={match.error.message}
        action={
          sansProfil ? (
            <Link href="/cv-studio" className={buttonVariants({ variant: "primary" })}>
              Valider mon profil
            </Link>
          ) : (
            <Button onClick={() => void match.refetch()}>Réessayer</Button>
          )
        }
      />
    );
  }

  const { result, profile_version: versionProfil, computed_at: calculeLe } = match.data;
  const skills = result.criteria.find((c) => c.criterion === "skills");
  const couverture = Math.round(Number(result.coverage) * 100);

  return (
    <section aria-label="Compatibilité avec votre profil" className="flex flex-col gap-4">
      <Panel title="Compatibilité">
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-start gap-6">
            <ScoreIndicator score={result.score} reliability={result.reliability} size="large" />
            <p className="max-w-prose flex-1 text-sm text-foreground">{result.summary}</p>
          </div>
          {result.score !== null ? (
            <p className="text-xs text-foreground-muted">
              Score calculé sur {couverture} % du poids des critères (les critères sans données ne
              comptent pas). Basé sur la version {versionProfil} de votre profil, calculé le{" "}
              {formatDate(calculeLe)}.
            </p>
          ) : null}
          <p className="rounded-md bg-background-secondary p-3 text-xs text-foreground-muted">
            {result.disclaimer}
          </p>
        </div>
      </Panel>
      {skills ? <SkillMatchPanel items={skills.items} /> : null}
      <CriteriaBreakdown criteria={result.criteria} />
    </section>
  );
}
