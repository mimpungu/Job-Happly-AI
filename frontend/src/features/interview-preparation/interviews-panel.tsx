"use client";

import { CalendarClock } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "@/components/ui/toaster";
import { formatDateTime } from "@/features/applications/format";
import type { Interview } from "@/types/interviews";

import { InterviewForm } from "./interview-form";
import { FORMAT_LABELS, OUTCOME_LABELS, STAGE_LABELS } from "./labels";
import { useFollowUp, useInterviews } from "./use-interviews";

export function InterviewsPanel({ applicationId }: { applicationId: string }) {
  const entretiens = useInterviews(applicationId);
  const [edition, setEdition] = useState<string | "new" | null>(null);

  if (entretiens.isPending) {
    return <Skeleton className="h-40 w-full" role="status" aria-label="Chargement" />;
  }
  if (entretiens.isError) {
    return (
      <EmptyState
        title="Impossible de charger les entretiens"
        description={entretiens.error.message}
        action={<Button onClick={() => void entretiens.refetch()}>Réessayer</Button>}
      />
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {edition === "new" ? (
        <Panel title="Nouvel entretien">
          <InterviewForm applicationId={applicationId} onDone={() => setEdition(null)} />
        </Panel>
      ) : (
        <div>
          <Button onClick={() => setEdition("new")}>Ajouter un entretien</Button>
        </div>
      )}

      {entretiens.data.length === 0 && edition !== "new" ? (
        <EmptyState
          icon={CalendarClock}
          title="Aucun entretien enregistré"
          description="Notez la date, les interlocuteurs et votre retour : tout reste dans l'historique de la candidature."
        />
      ) : null}

      {entretiens.data.map((e) =>
        edition === e.id ? (
          <Panel key={e.id} title={STAGE_LABELS[e.stage]}>
            <InterviewForm
              applicationId={applicationId}
              interview={e}
              onDone={() => setEdition(null)}
            />
          </Panel>
        ) : (
          <InterviewCard
            key={e.id}
            applicationId={applicationId}
            interview={e}
            onEdit={() => setEdition(e.id)}
          />
        ),
      )}
    </div>
  );
}

function InterviewCard({
  applicationId,
  interview,
  onEdit,
}: {
  applicationId: string;
  interview: Interview;
  onEdit: () => void;
}) {
  const { draft, schedule } = useFollowUp(applicationId, interview.id);
  const brouillon = interview.follow_up_draft;

  const copier = async () => {
    if (!brouillon) return;
    try {
      await navigator.clipboard.writeText(`${brouillon.subject}\n\n${brouillon.body}`);
      toast.success("Brouillon copié.");
    } catch {
      toast.error("Copie impossible : sélectionnez le texte manuellement.");
    }
  };

  return (
    <Panel
      title={STAGE_LABELS[interview.stage]}
      actions={
        <Button variant="secondary" size="sm" onClick={onEdit}>
          Modifier
        </Button>
      }
    >
      <div className="flex flex-col gap-4 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={interview.outcome === "positive" ? "success" : "neutral"}>
            {OUTCOME_LABELS[interview.outcome]}
          </Badge>
          <span>{formatDateTime(interview.scheduled_at)}</span>
          <span className="text-foreground-muted">{FORMAT_LABELS[interview.format]}</span>
          {interview.location ? (
            <span className="text-foreground-muted">{interview.location}</span>
          ) : null}
        </div>
        {interview.interviewers.length > 0 ? (
          <p>Avec : {interview.interviewers.join(", ")}</p>
        ) : null}
        {interview.notes ? <p className="whitespace-pre-line">{interview.notes}</p> : null}
        {interview.feedback_notes ? (
          <p className="whitespace-pre-line">
            <strong>Retour : </strong>
            {interview.feedback_notes}
          </p>
        ) : null}

        <div className="flex flex-col gap-3 border-t border-border pt-4">
          <p className="font-medium">Relance après l&apos;entretien</p>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              size="sm"
              loading={draft.isPending}
              onClick={() =>
                draft.mutate(undefined, { onError: (erreur) => toast.error(erreur.message) })
              }
            >
              {brouillon ? "Régénérer le brouillon" : "Préparer un brouillon de remerciement"}
            </Button>
            {brouillon ? (
              <>
                <Button variant="secondary" size="sm" onClick={() => void copier()}>
                  Copier le brouillon
                </Button>
                <Button
                  size="sm"
                  loading={schedule.isPending}
                  onClick={() =>
                    schedule.mutate(undefined, {
                      onSuccess: (r) =>
                        toast.success(`Relance planifiée le ${formatDateTime(r.follow_up_at)}.`),
                      onError: (erreur) => toast.error(erreur.message),
                    })
                  }
                >
                  Planifier la relance ({formatDateTime(brouillon.suggested_follow_up_at)})
                </Button>
              </>
            ) : null}
          </div>
          {brouillon ? (
            <div className="rounded-md border border-border p-3">
              <p className="font-medium">{brouillon.subject}</p>
              <p className="mt-2 whitespace-pre-line">{brouillon.body}</p>
              <p className="mt-2 text-xs text-foreground-muted">
                Rien n&apos;est envoyé par l&apos;application : copiez le texte, complétez le
                passage entre crochets puis envoyez-le vous-même.
              </p>
            </div>
          ) : null}
        </div>
      </div>
    </Panel>
  );
}
