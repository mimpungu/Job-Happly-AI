"use client";

import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { Field } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "@/components/ui/toaster";
import { cn } from "@/lib/cn";
import { EXPORT_URL } from "@/services/privacy";
import type { PersonalDataPolicy } from "@/types/privacy";

import { EraseDialog } from "./erase-dialog";
import {
  useAiTransfers,
  usePrivacySettings,
  usePrivacySummary,
  usePurge,
  useRetention,
  useSetPolicy,
} from "./use-privacy";

const POLICIES: { value: PersonalDataPolicy; label: string }[] = [
  { value: "allowed", label: "Autorisé selon mes réglages IA (consentement, plafond)" },
  { value: "local_only", label: "Modèle local uniquement (rien ne quitte ma machine)" },
  { value: "never", label: "Jamais : aucune IA ne reçoit mes données personnelles" },
];

function taille(octets: number): string {
  if (octets === 0) return "—";
  return octets < 1024 * 1024
    ? `${Math.max(1, Math.round(octets / 1024))} Ko`
    : `${(octets / (1024 * 1024)).toFixed(1)} Mo`;
}

function ErreurPanneau({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div role="alert" className="flex items-center gap-3 text-sm">
      <span>{message}</span>
      <Button size="sm" variant="secondary" onClick={onRetry}>
        Réessayer
      </Button>
    </div>
  );
}

export function PrivacyPanel() {
  const resume = usePrivacySummary();
  const reglages = usePrivacySettings();
  const politique = useSetPolicy();
  const retention = useRetention();
  const transferts = useAiTransfers();
  const purge = usePurge();

  return (
    <div className="flex flex-col gap-6">
      <Panel
        title="Mes données"
        actions={
          <a
            href={EXPORT_URL}
            download
            className={cn(buttonVariants({ variant: "secondary", size: "sm" }))}
          >
            Exporter mes données (ZIP)
          </a>
        }
      >
        {resume.isPending ? (
          <Skeleton className="h-32 w-full" role="status" aria-label="Chargement" />
        ) : resume.isError ? (
          <ErreurPanneau message={resume.error.message} onRetry={() => void resume.refetch()} />
        ) : (
          <div className="flex flex-col gap-4">
            <p className="text-sm text-foreground-muted">
              Tout reste sur votre machine. L&apos;export contient un fichier par table et vos PDF
              générés. La suppression est définitive et demande une confirmation saisie.
            </p>
            <ul className="flex flex-col divide-y divide-border">
              {resume.data.map((c) => (
                <li
                  key={c.category}
                  className="flex flex-wrap items-center justify-between gap-3 py-3 text-sm"
                >
                  <div className="flex flex-col">
                    <span>{c.label}</span>
                    <span className="text-foreground-muted">
                      {c.rows} ligne(s)
                      {c.file_bytes > 0 ? ` · fichiers ${taille(c.file_bytes)}` : ""}
                    </span>
                  </div>
                  <EraseDialog
                    scope={c.category}
                    label={c.label}
                    triggerLabel={`Supprimer ${c.label.split(" (")[0]?.toLowerCase() ?? ""}`}
                  />
                </li>
              ))}
            </ul>
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4 text-sm">
              <span>Tout supprimer et repartir de zéro</span>
              <EraseDialog scope="all" label="toutes vos données" triggerLabel="Tout supprimer" />
            </div>
          </div>
        )}
      </Panel>

      <Panel title="Données personnelles et IA">
        {reglages.isPending ? (
          <Skeleton className="h-16 w-full" role="status" aria-label="Chargement" />
        ) : reglages.isError ? (
          <ErreurPanneau message={reglages.error.message} onRetry={() => void reglages.refetch()} />
        ) : (
          <div className="flex flex-col gap-4">
            <div className="max-w-xl">
              <Field
                label="Envoi de mes données personnelles à une IA"
                hint="S'applique au CV, au profil et à vos réponses d'entretien. Les textes d'offres publiques ne sont pas concernés."
              >
                {(champ) => (
                  <Select
                    {...champ}
                    value={reglages.data.personal_data_policy}
                    options={POLICIES}
                    disabled={politique.isPending}
                    onChange={(e) =>
                      politique.mutate(e.target.value as PersonalDataPolicy, {
                        onSuccess: () => toast.success("Réglage de confidentialité enregistré."),
                        onError: (erreur) => toast.error(erreur.message),
                      })
                    }
                  />
                )}
              </Field>
            </div>
            {transferts.data ? (
              <details className="rounded-md border border-border p-3 text-sm">
                <summary className="cursor-pointer font-medium">
                  Ce qui peut être envoyé à un fournisseur d&apos;IA
                </summary>
                <ul className="mt-3 flex flex-col gap-3">
                  {transferts.data.map((t) => (
                    <li key={t.task_type} className="flex flex-col gap-1">
                      <span className="flex flex-wrap items-center gap-2 font-medium">
                        {t.purpose}
                        <Badge variant={t.personal_data ? "warning" : "success"}>
                          {t.personal_data ? "Données personnelles" : "Sans donnée personnelle"}
                        </Badge>
                      </span>
                      <span>
                        <strong>Envoyé : </strong>
                        {t.data_sent}
                      </span>
                      <span className="text-foreground-muted">
                        <strong>Jamais envoyé : </strong>
                        {t.never_sent}
                      </span>
                    </li>
                  ))}
                </ul>
              </details>
            ) : null}
          </div>
        )}
      </Panel>

      <Panel
        title="Conservation"
        actions={
          <Button
            variant="secondary"
            size="sm"
            loading={purge.isPending}
            onClick={() =>
              purge.mutate(undefined, {
                onSuccess: (r) =>
                  toast.success(
                    `${Object.values(r.rows_purged).reduce((a, b) => a + b, 0)} ligne(s) expirée(s) purgée(s).`,
                  ),
                onError: (erreur) => toast.error(erreur.message),
              })
            }
          >
            Purger les données expirées
          </Button>
        }
      >
        {retention.isPending ? (
          <Skeleton className="h-24 w-full" role="status" aria-label="Chargement" />
        ) : retention.isError ? (
          <ErreurPanneau
            message={retention.error.message}
            onRetry={() => void retention.refetch()}
          />
        ) : (
          <ul className="flex flex-col gap-2 text-sm">
            {retention.data.map((r) => (
              <li key={r.table} className="flex flex-wrap items-center justify-between gap-2">
                <span>{r.description}</span>
                <span className="text-foreground-muted">
                  {r.days === null ? "Jusqu'à suppression par vous" : `${r.days} jours`}
                  {r.automatic ? " · purge automatique" : ""}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
