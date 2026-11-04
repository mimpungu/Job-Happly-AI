"use client";

import { useState, type FormEvent } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/input";
import { toast } from "@/components/ui/toaster";
import type { ApplicationDetail } from "@/types/applications";

import { formatDateTime, isOverdue, localInputToIso } from "./format";
import { useSetFollowUp } from "./use-applications";

/** Date de relance : planifiable seulement une fois la candidature envoyée. */
export function FollowUpPanel({ application }: { application: ApplicationDetail }) {
  const planifier = useSetFollowUp(application.id);
  const [quand, setQuand] = useState("");
  const [notes, setNotes] = useState("");
  const envoyee = application.applied_at !== null;

  const soumettre = (e: FormEvent) => {
    e.preventDefault();
    const at = localInputToIso(quand);
    if (!at) return;
    planifier.mutate(
      { at, notes: notes.trim() || undefined },
      {
        onSuccess: () => {
          toast.success("Relance planifiée.");
          setQuand("");
          setNotes("");
        },
        onError: (erreur) => toast.error(erreur.message),
      },
    );
  };

  return (
    <Panel title="Relance">
      <div className="flex flex-col gap-4">
        {application.follow_up_at ? (
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <span>Prévue le {formatDateTime(application.follow_up_at)}</span>
            {isOverdue(application.follow_up_at) ? <Badge variant="warning">Échue</Badge> : null}
            <Button
              variant="ghost"
              size="sm"
              loading={planifier.isPending}
              onClick={() =>
                planifier.mutate(
                  { at: null },
                  {
                    onSuccess: () => toast.success("Relance annulée."),
                    onError: (erreur) => toast.error(erreur.message),
                  },
                )
              }
            >
              Annuler la relance
            </Button>
          </div>
        ) : (
          <p className="text-sm text-foreground-muted">Aucune relance planifiée.</p>
        )}

        {envoyee ? (
          <form
            onSubmit={soumettre}
            className="grid gap-3 md:grid-cols-2"
            aria-label="Planifier une relance"
          >
            <Field label="Date et heure de relance">
              {(c) => (
                <Input
                  {...c}
                  type="datetime-local"
                  value={quand}
                  required
                  onChange={(e) => setQuand(e.target.value)}
                />
              )}
            </Field>
            <Field label="Note (facultatif)">
              {(c) => (
                <Input
                  {...c}
                  value={notes}
                  maxLength={1000}
                  onChange={(e) => setNotes(e.target.value)}
                />
              )}
            </Field>
            <div className="md:col-span-2">
              <Button
                type="submit"
                variant="secondary"
                disabled={!quand}
                loading={planifier.isPending}
              >
                Planifier la relance
              </Button>
            </div>
          </form>
        ) : (
          <p className="text-sm text-foreground-muted">
            Une relance se planifie une fois la candidature envoyée.
          </p>
        )}
      </div>
    </Panel>
  );
}
