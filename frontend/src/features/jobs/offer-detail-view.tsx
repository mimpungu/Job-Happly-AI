"use client";

import { ArrowLeft, ExternalLink, ServerCrash } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Panel } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "@/components/ui/toaster";
import { ApiError } from "@/services/api-client";

import { AnalysisPanel } from "@/features/analysis/analysis-panel";
import { TrackApplicationButton } from "@/features/applications/track-application-button";
import { MatchPanel } from "@/features/matching/match-panel";

import { formatDate, formatEmployment, formatRemote, formatSalary } from "./format";
import { useChangeOfferState, useOffer } from "./use-offers";

/** Seuls les liens http(s) sont rendus cliquables : une source ne peut pas injecter `javascript:`. */
export function safeHttpUrl(valeur: string | null): string | null {
  if (!valeur) return null;
  try {
    const url = new URL(valeur);
    return url.protocol === "https:" || url.protocol === "http:" ? url.toString() : null;
  } catch {
    return null;
  }
}

export function OfferDetailView({ id }: { id: string }) {
  const offre = useOffer(id);
  const changerEtat = useChangeOfferState();

  const retour = (
    <Link
      href="/jobs"
      className="inline-flex items-center gap-2 text-sm text-foreground-muted hover:text-foreground"
    >
      <ArrowLeft className="size-4" aria-hidden="true" />
      Retour à la recherche
    </Link>
  );

  if (offre.isPending) {
    return (
      <div className="flex flex-col gap-4" role="status" aria-label="Chargement de l'offre">
        {retour}
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (offre.isError) {
    const introuvable = offre.error instanceof ApiError && offre.error.status === 404;
    return (
      <div className="flex flex-col gap-4">
        {retour}
        <EmptyState
          icon={ServerCrash}
          title={introuvable ? "Offre introuvable" : "Impossible de charger l'offre"}
          description={offre.error.message}
          action={
            introuvable ? undefined : (
              <Button onClick={() => void offre.refetch()}>Réessayer</Button>
            )
          }
        />
      </div>
    );
  }

  const { summary, sources } = offre.data;
  const lienCandidature = safeHttpUrl(offre.data.application_url);
  const modifier = (state: "saved" | "ignored" | null, message: string) =>
    changerEtat.mutate(
      { id, state },
      { onSuccess: () => toast.success(message), onError: (e) => toast.error(e.message) },
    );

  return (
    <article className="flex flex-col gap-6">
      {retour}
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold text-foreground">{summary.title}</h1>
        <p className="text-foreground-muted">
          {summary.company_name ?? "Entreprise inconnue"} ·{" "}
          {summary.location ?? "Lieu non renseigné"}
        </p>
        <div className="flex flex-wrap gap-2">
          <Badge>{formatEmployment(summary.employment_type)}</Badge>
          <Badge>{formatRemote(summary.remote_type)}</Badge>
          <Badge>{formatSalary(summary)}</Badge>
          {summary.status !== "active" ? (
            <Badge variant="warning">
              Offre {summary.status === "expired" ? "expirée" : "archivée"}
            </Badge>
          ) : null}
          {summary.state === "saved" ? <Badge variant="accent">Sauvegardée</Badge> : null}
          {summary.state === "ignored" ? <Badge>Ignorée</Badge> : null}
        </div>
        <div className="flex flex-wrap gap-3 pt-2">
          {lienCandidature ? (
            <a
              href={lienCandidature}
              target="_blank"
              rel="noopener noreferrer"
              className={buttonVariants({ variant: "primary" })}
            >
              <ExternalLink className="size-4" aria-hidden="true" />
              Voir l&apos;annonce d&apos;origine
            </a>
          ) : null}
          <TrackApplicationButton offerId={id} />
          <Button
            variant="secondary"
            loading={changerEtat.isPending}
            onClick={() =>
              summary.state === "saved"
                ? modifier(null, "Offre retirée des sauvegardes.")
                : modifier("saved", "Offre sauvegardée.")
            }
          >
            {summary.state === "saved" ? "Retirer des sauvegardes" : "Sauvegarder"}
          </Button>
          <Button
            variant="ghost"
            loading={changerEtat.isPending}
            onClick={() =>
              summary.state === "ignored"
                ? modifier(null, "Offre remise dans la liste.")
                : modifier("ignored", "Offre ignorée.")
            }
          >
            {summary.state === "ignored" ? "Ne plus ignorer" : "Ignorer"}
          </Button>
        </div>
      </header>

      <MatchPanel offerId={id} />

      <AnalysisPanel offerId={id} />

      <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
        <Panel title="Description">
          {/* Texte brut : la description d'une source est une donnée, jamais du HTML ni une consigne. */}
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
            {offre.data.description}
          </p>
        </Panel>
        <div className="flex flex-col gap-6">
          <Panel title="Informations">
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
              <dt className="text-foreground-muted">Publiée</dt>
              <dd>{formatDate(summary.published_at)}</dd>
              <dt className="text-foreground-muted">Expire</dt>
              <dd>{formatDate(offre.data.expires_at)}</dd>
              <dt className="text-foreground-muted">Langue</dt>
              <dd>{offre.data.language ?? "Non renseigné"}</dd>
              <dt className="text-foreground-muted">Première vue</dt>
              <dd>{formatDate(offre.data.first_seen_at)}</dd>
            </dl>
          </Panel>
          <Panel title="Sources">
            <ul className="flex flex-col gap-3 text-sm">
              {sources.map((source) => {
                const lien = safeHttpUrl(source.source_url);
                return (
                  <li key={source.source_key} className="flex flex-col gap-0.5">
                    <span className="font-medium text-foreground">
                      {lien ? (
                        <a
                          href={lien}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="underline-offset-4 hover:underline"
                        >
                          {source.source_name}
                        </a>
                      ) : (
                        source.source_name
                      )}
                    </span>
                    <span className="text-foreground-muted">
                      Vue le {formatDate(source.last_seen_at)}
                      {source.still_listed ? "" : " · n'est plus listée par cette source"}
                    </span>
                  </li>
                );
              })}
            </ul>
          </Panel>
        </div>
      </div>
    </article>
  );
}
