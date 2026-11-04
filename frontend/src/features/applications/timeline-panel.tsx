"use client";

import { useState, type FormEvent } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/input";
import { statusLabel } from "@/components/ui/status-badge";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/toaster";
import type { ApplicationDetail, TimelineEvent } from "@/types/applications";

import { EVENT_LABELS, formatDateTime, localInputToIso } from "./format";
import { useAddInterview, useAddNote } from "./use-applications";

function description(evenement: TimelineEvent): string {
  if (evenement.kind === "status_change" && evenement.to_status) {
    const vers = statusLabel(evenement.to_status);
    return evenement.from_status ? `${statusLabel(evenement.from_status)} → ${vers}` : vers;
  }
  return evenement.body ?? "";
}

/** Historique ordonné et saisie des notes et entretiens. */
export function TimelinePanel({ application }: { application: ApplicationDetail }) {
  const ajouterNote = useAddNote(application.id);
  const ajouterEntretien = useAddInterview(application.id);
  const [note, setNote] = useState("");
  const [entretien, setEntretien] = useState("");
  const [quand, setQuand] = useState("");

  const soumettreNote = (e: FormEvent) => {
    e.preventDefault();
    ajouterNote.mutate(note.trim(), {
      onSuccess: () => setNote(""),
      onError: (erreur) => toast.error(erreur.message),
    });
  };
  const soumettreEntretien = (e: FormEvent) => {
    e.preventDefault();
    ajouterEntretien.mutate(
      { description: entretien.trim(), time: localInputToIso(quand) },
      {
        onSuccess: () => {
          setEntretien("");
          setQuand("");
        },
        onError: (erreur) => toast.error(erreur.message),
      },
    );
  };

  return (
    <Panel title="Historique">
      <div className="flex flex-col gap-5">
        <ol className="flex flex-col gap-3" aria-label="Historique de la candidature">
          {application.events.map((e) => (
            <li key={e.id} className="flex flex-col gap-0.5 border-l-2 border-border pl-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge>{EVENT_LABELS[e.kind]}</Badge>
                <span className="text-xs text-foreground-muted">
                  {formatDateTime(e.occurred_at)}
                </span>
              </div>
              <p className="text-sm text-foreground">{description(e)}</p>
              {e.kind === "status_change" && e.body ? (
                <p className="text-xs text-foreground-muted">{e.body}</p>
              ) : null}
            </li>
          ))}
        </ol>

        <form
          onSubmit={soumettreNote}
          className="flex flex-col gap-2"
          aria-label="Ajouter une note"
        >
          <Field label="Nouvelle note">
            {(c) => (
              <Textarea
                {...c}
                value={note}
                maxLength={5000}
                onChange={(e) => setNote(e.target.value)}
              />
            )}
          </Field>
          <div>
            <Button
              type="submit"
              variant="secondary"
              disabled={!note.trim()}
              loading={ajouterNote.isPending}
            >
              Ajouter la note
            </Button>
          </div>
        </form>

        <form
          onSubmit={soumettreEntretien}
          className="grid gap-3 md:grid-cols-2"
          aria-label="Ajouter un entretien"
        >
          <Field label="Entretien ou échange">
            {(c) => (
              <Input
                {...c}
                value={entretien}
                maxLength={5000}
                onChange={(e) => setEntretien(e.target.value)}
              />
            )}
          </Field>
          <Field label="Date et heure (facultatif)">
            {(c) => (
              <Input
                {...c}
                type="datetime-local"
                value={quand}
                onChange={(e) => setQuand(e.target.value)}
              />
            )}
          </Field>
          <div className="md:col-span-2">
            <Button
              type="submit"
              variant="secondary"
              disabled={!entretien.trim()}
              loading={ajouterEntretien.isPending}
            >
              Ajouter l&apos;entretien
            </Button>
          </div>
        </form>
      </div>
    </Panel>
  );
}
