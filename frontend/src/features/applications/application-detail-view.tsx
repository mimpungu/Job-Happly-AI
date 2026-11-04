"use client";

import { ArrowLeft, ServerCrash } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import { ApiError } from "@/services/api-client";

import { ContactsPanel } from "./contacts-panel";
import { DeleteApplicationButton } from "./delete-application-button";
import { DossierPanel } from "./dossier-panel";
import { FollowUpPanel } from "./follow-up-panel";
import { formatDateTime } from "./format";
import { StatusActions } from "./status-actions";
import { TimelinePanel } from "./timeline-panel";
import { useApplication } from "./use-applications";

export function ApplicationDetailView({ id }: { id: string }) {
  const candidature = useApplication(id);

  const retour = (
    <Link
      href="/applications"
      className="inline-flex items-center gap-2 text-sm text-foreground-muted hover:text-foreground"
    >
      <ArrowLeft className="size-4" aria-hidden="true" />
      Retour aux candidatures
    </Link>
  );

  if (candidature.isPending) {
    return (
      <div className="flex flex-col gap-4" role="status" aria-label="Chargement de la candidature">
        {retour}
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (candidature.isError) {
    const introuvable = candidature.error instanceof ApiError && candidature.error.status === 404;
    return (
      <div className="flex flex-col gap-4">
        {retour}
        <EmptyState
          icon={ServerCrash}
          title={introuvable ? "Candidature introuvable" : "Impossible de charger la candidature"}
          description={candidature.error.message}
          action={
            introuvable ? undefined : (
              <Button onClick={() => void candidature.refetch()}>Réessayer</Button>
            )
          }
        />
      </div>
    );
  }

  const c = candidature.data;
  return (
    <div className="flex flex-col gap-6">
      {retour}
      <header className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold text-foreground">
            {c.offer?.title ?? "Offre introuvable"}
          </h1>
          <StatusBadge status={c.status} />
          <span className="ml-auto">
            <DeleteApplicationButton applicationId={c.id} />
          </span>
        </div>
        <p className="text-foreground-muted">
          {c.offer?.company_name ?? "Entreprise inconnue"}
          {c.offer?.location ? ` · ${c.offer.location}` : ""}
        </p>
        <p className="text-sm text-foreground-muted">
          {c.applied_at
            ? `Envoyée le ${formatDateTime(c.applied_at)}`
            : "Pas encore envoyée : vous candidatez vous-même sur le site de l'employeur."}
          {c.offer ? (
            <>
              {" · "}
              <Link
                href={`/jobs/${c.offer.offer_id}`}
                className="text-accent underline underline-offset-4"
              >
                Voir l&apos;offre
              </Link>
              {" · "}
              <Link
                href={`/interview-preparation?application=${c.id}`}
                className="text-accent underline underline-offset-4"
              >
                Préparer l&apos;entretien
              </Link>
            </>
          ) : null}
        </p>
      </header>

      <StatusActions application={c} />

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="flex flex-col gap-6">
          <DossierPanel application={c} />
          <FollowUpPanel application={c} />
          <ContactsPanel application={c} />
        </div>
        <TimelinePanel application={c} />
      </div>
    </div>
  );
}
