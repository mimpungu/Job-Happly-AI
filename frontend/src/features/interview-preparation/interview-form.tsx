"use client";

import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/toaster";
import { isoToLocalInput, localInputToIso } from "@/features/applications/format";
import type {
  Interview,
  InterviewFormat,
  InterviewOutcome,
  InterviewStage,
} from "@/types/interviews";

import { FORMAT_LABELS, OUTCOME_LABELS, STAGE_LABELS, options } from "./labels";
import { useSaveInterview } from "./use-interviews";

/** Création ou modification d'une fiche ; la date est saisie en heure locale, envoyée avec son fuseau. */
export function InterviewForm({
  applicationId,
  interview,
  onDone,
}: {
  applicationId: string;
  interview?: Interview;
  onDone: () => void;
}) {
  const enregistrer = useSaveInterview(applicationId, interview?.id);
  const [stage, setStage] = useState<InterviewStage>(interview?.stage ?? "other");
  const [format, setFormat] = useState<InterviewFormat>(interview?.format ?? "other");
  const [quand, setQuand] = useState(
    interview?.scheduled_at ? isoToLocalInput(new Date(interview.scheduled_at)) : "",
  );
  const [lieu, setLieu] = useState(interview?.location ?? "");
  const [interlocuteurs, setInterlocuteurs] = useState(interview?.interviewers.join(", ") ?? "");
  const [notes, setNotes] = useState(interview?.notes ?? "");
  const [issue, setIssue] = useState<InterviewOutcome>(interview?.outcome ?? "pending");
  const [retour, setRetour] = useState(interview?.feedback_notes ?? "");

  const soumettre = (e: FormEvent) => {
    e.preventDefault();
    enregistrer.mutate(
      {
        stage,
        format,
        scheduled_at: localInputToIso(quand) ?? null,
        location: lieu.trim() || null,
        interviewers: interlocuteurs
          .split(",")
          .map((p) => p.trim())
          .filter(Boolean),
        notes: notes.trim() || null,
        outcome: issue,
        feedback_notes: retour.trim() || null,
      },
      {
        onSuccess: () => {
          toast.success(interview ? "Entretien mis à jour." : "Entretien enregistré.");
          onDone();
        },
        onError: (erreur) => toast.error(erreur.message),
      },
    );
  };

  return (
    <form onSubmit={soumettre} className="grid gap-4 sm:grid-cols-2" aria-label="Fiche d'entretien">
      <Field label="Type d'entretien">
        {(c) => (
          <Select
            {...c}
            value={stage}
            options={options(STAGE_LABELS)}
            onChange={(e) => setStage(e.target.value as InterviewStage)}
          />
        )}
      </Field>
      <Field label="Format">
        {(c) => (
          <Select
            {...c}
            value={format}
            options={options(FORMAT_LABELS)}
            onChange={(e) => setFormat(e.target.value as InterviewFormat)}
          />
        )}
      </Field>
      <Field label="Date et heure" hint="Heure locale ; le fuseau est enregistré avec la date.">
        {(c) => (
          <Input
            {...c}
            type="datetime-local"
            value={quand}
            onChange={(e) => setQuand(e.target.value)}
          />
        )}
      </Field>
      <Field label="Lieu ou lien">
        {(c) => (
          <Input {...c} maxLength={300} value={lieu} onChange={(e) => setLieu(e.target.value)} />
        )}
      </Field>
      <Field label="Interlocuteurs" hint="Séparés par des virgules.">
        {(c) => (
          <Input
            {...c}
            value={interlocuteurs}
            onChange={(e) => setInterlocuteurs(e.target.value)}
          />
        )}
      </Field>
      <Field label="Issue">
        {(c) => (
          <Select
            {...c}
            value={issue}
            options={options(OUTCOME_LABELS)}
            onChange={(e) => setIssue(e.target.value as InterviewOutcome)}
          />
        )}
      </Field>
      <div className="sm:col-span-2">
        <Field label="Notes de préparation">
          {(c) => (
            <Textarea
              {...c}
              maxLength={5000}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          )}
        </Field>
      </div>
      <div className="sm:col-span-2">
        <Field label="Retour après l'entretien">
          {(c) => (
            <Textarea
              {...c}
              maxLength={5000}
              value={retour}
              onChange={(e) => setRetour(e.target.value)}
            />
          )}
        </Field>
      </div>
      <div className="flex gap-2 sm:col-span-2">
        <Button type="submit" loading={enregistrer.isPending}>
          Enregistrer
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          Annuler
        </Button>
      </div>
    </form>
  );
}
