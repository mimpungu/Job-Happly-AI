"use client";

import { CircleCheck, CircleX, TriangleAlert } from "lucide-react";
import { useState, type FormEvent } from "react";

import { Badge } from "@/components/ui/badge";
import { Panel } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "@/components/ui/toaster";
import type { ApplicationDetail, DocumentChoice } from "@/types/applications";

import { useAttachDocuments, useDocumentChoices, useDossier } from "./use-applications";

function Piece({ present, label }: { present: boolean; label: string }) {
  const Icone = present ? CircleCheck : CircleX;
  return (
    <li className="flex items-center gap-2 text-sm">
      <Icone
        className={present ? "size-4 text-success" : "size-4 text-danger"}
        aria-hidden="true"
      />
      <span>
        {label} : {present ? "présent" : "manquant"}
      </span>
    </li>
  );
}

/** Dossier de candidature : pièces requises, avertissements de qualité, documents associés. */
export function DossierPanel({ application }: { application: ApplicationDetail }) {
  const dossier = useDossier(application.id);
  const choix = useDocumentChoices();
  const associer = useAttachDocuments(application.id);
  const [cv, setCv] = useState("");
  const [lettre, setLettre] = useState("");

  const options = (kind: DocumentChoice["kind"]) =>
    (choix.data ?? [])
      .filter((c) => c.kind === kind)
      .map((c) => ({ value: c.versionId, label: c.label }));

  const soumettre = (e: FormEvent) => {
    e.preventDefault();
    associer.mutate(
      { cvVersionId: cv || undefined, letterVersionId: lettre || undefined },
      {
        onSuccess: () => {
          toast.success("Documents associés.");
          setCv("");
          setLettre("");
        },
        onError: (erreur) => toast.error(erreur.message),
      },
    );
  };

  return (
    <Panel title="Dossier de candidature">
      {dossier.isPending ? (
        <Skeleton className="h-24 w-full" />
      ) : dossier.isError ? (
        <p role="alert" className="text-sm text-danger">
          {dossier.error.message}
        </p>
      ) : (
        <div className="flex flex-col gap-4">
          <p className="text-sm text-foreground-muted">
            {dossier.data.is_ready_to_send
              ? "Le dossier est complet."
              : "Le dossier est incomplet : il doit l'être pour passer au statut « Prête à envoyer »."}
          </p>
          <ul className="flex flex-col gap-1.5" aria-label="Pièces du dossier">
            <Piece present={dossier.data.has_cv} label="CV personnalisé" />
            <Piece present={dossier.data.has_letter} label="Lettre de motivation" />
            <Piece present={dossier.data.application_url !== null} label="Lien de candidature" />
          </ul>
          {dossier.data.warnings.map((alerte) => (
            <p key={alerte} className="flex items-start gap-2 text-sm text-warning">
              <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              {alerte}
            </p>
          ))}

          {application.documents.length > 0 ? (
            <ul className="flex flex-col gap-1.5" aria-label="Documents associés">
              {application.documents.map((d) => (
                <li
                  key={d.document_version_id}
                  className="flex flex-wrap items-center gap-2 text-sm"
                >
                  <Badge>{d.kind === "cv" ? "CV" : "Lettre"}</Badge>
                  {d.title} — v{d.version}
                  {d.is_current ? <Badge variant="accent">Retenue</Badge> : null}
                  {d.quality_passed === false ? (
                    <Badge variant="warning">Audit non conforme</Badge>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : null}

          <form
            onSubmit={soumettre}
            className="grid gap-3 md:grid-cols-2"
            aria-label="Associer des documents"
          >
            <Field
              label="Version du CV"
              hint={
                application.applied_at ? "Un CV déjà envoyé ne peut plus être remplacé." : undefined
              }
            >
              {({ id }) => (
                <Select
                  id={id}
                  options={options("cv")}
                  placeholder="Aucun changement"
                  value={cv}
                  onChange={(e) => setCv(e.target.value)}
                />
              )}
            </Field>
            <Field label="Version de la lettre">
              {({ id }) => (
                <Select
                  id={id}
                  options={options("cover_letter")}
                  placeholder="Aucun changement"
                  value={lettre}
                  onChange={(e) => setLettre(e.target.value)}
                />
              )}
            </Field>
            <div className="md:col-span-2">
              <Button
                type="submit"
                variant="secondary"
                disabled={!cv && !lettre}
                loading={associer.isPending}
              >
                Associer
              </Button>
            </div>
          </form>
        </div>
      )}
    </Panel>
  );
}
