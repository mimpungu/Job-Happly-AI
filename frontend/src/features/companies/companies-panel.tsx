"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "@/components/ui/toaster";
import type { CollectionReport, Company, DiscoveredBoard } from "@/types/companies";

import {
  useAddCompany,
  useCompanies,
  useDiscoverCompany,
  useRunCollection,
  useSetCompanyEnabled,
} from "./use-companies";

const ATS_LABELS: Record<string, string> = { greenhouse: "Greenhouse", lever: "Lever" };

function pluriel(n: number, mot: string) {
  return `${n} ${mot}${n > 1 ? "s" : ""}`;
}

/** Résumé d'une collecte : les erreurs sont nommées, jamais transformées en « 0 offre ». */
export function resumeCollecte(rapport: CollectionReport): string {
  const nouvelles = rapport.sources.reduce((somme, s) => somme + s.created, 0);
  const echecs = rapport.sources.filter((s) => !s.succeeded).length;
  const base = `${pluriel(rapport.sources.length, "source")} interrogée${
    rapport.sources.length > 1 ? "s" : ""
  } · ${`${nouvelles} ${nouvelles > 1 ? "nouvelles offres" : "nouvelle offre"}`}`;
  return echecs > 0 ? `${base} · ${pluriel(echecs, "source")} en échec` : base;
}

function Recherche() {
  const [nom, setNom] = useState("");
  const [interroge, setInterroge] = useState("");
  const decouvrir = useDiscoverCompany();
  const ajouter = useAddCompany();

  const lancer = () => {
    const saisie = nom.trim();
    if (saisie.length < 2) return;
    setInterroge(saisie);
    decouvrir.mutate(saisie, { onError: (e) => toast.error(e.message) });
  };

  const suivre = (board: DiscoveredBoard) =>
    ajouter.mutate(
      {
        name: board.board_name ?? interroge,
        careers_url: board.careers_url,
        enabled: true,
      },
      {
        onSuccess: () => {
          toast.success("Entreprise ajoutée. Lancez la collecte pour récupérer ses offres.");
          decouvrir.reset();
          setNom("");
        },
        onError: (e) => toast.error(e.message),
      },
    );

  return (
    <div className="flex flex-col gap-3">
      <form
        aria-label="Rechercher une entreprise"
        onSubmit={(e) => {
          e.preventDefault();
          lancer();
        }}
        className="flex flex-wrap items-end gap-3"
      >
        <div className="min-w-60 flex-1">
          <Field
            label="Nom de l'entreprise"
            hint="Tapez n'importe quelle entreprise : l'application cherche son site carrières public."
          >
            {(champ) => (
              <Input
                {...champ}
                value={nom}
                maxLength={100}
                placeholder="Ex. Stripe, Datadog, Spotify…"
                onChange={(e) => setNom(e.target.value)}
              />
            )}
          </Field>
        </div>
        <Button type="submit" loading={decouvrir.isPending} disabled={nom.trim().length < 2}>
          Chercher
        </Button>
      </form>

      {decouvrir.isSuccess ? (
        decouvrir.data.length === 0 ? (
          <p role="status" className="text-sm text-foreground-muted">
            Aucun site carrières public (Greenhouse ou Lever) trouvé pour « {interroge} ». Cela ne
            veut pas dire que l&apos;entreprise n&apos;a pas d&apos;offres : elle utilise peut-être
            un autre outil, non pris en charge. Essayez l&apos;orthographe exacte du nom, ou collez
            l&apos;adresse de sa page carrières ci-dessous.
          </p>
        ) : (
          <ul aria-label="Sites carrières trouvés" className="flex flex-col gap-2">
            {decouvrir.data.map((b) => (
              <li
                key={`${b.ats_kind}:${b.token}`}
                className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border px-3 py-2"
              >
                <div className="flex flex-col">
                  <span className="text-sm font-medium text-foreground">
                    {b.board_name ?? b.token} · {ATS_LABELS[b.ats_kind] ?? b.ats_kind}
                  </span>
                  <span className="text-xs text-foreground-muted">
                    {pluriel(b.offer_count, "offre")} publiée{b.offer_count > 1 ? "s" : ""} ·{" "}
                    {b.careers_url}
                  </span>
                </div>
                <Button
                  variant="secondary"
                  loading={ajouter.isPending}
                  onClick={() => suivre(b)}
                  aria-label={`Suivre ${b.board_name ?? b.token} (${ATS_LABELS[b.ats_kind] ?? b.ats_kind})`}
                >
                  Suivre
                </Button>
              </li>
            ))}
            <li className="text-xs text-foreground-muted">
              Vérifiez que c&apos;est bien la bonne entreprise : deux sociétés peuvent porter un nom
              proche.
            </li>
          </ul>
        )
      ) : null}
    </div>
  );
}

function AjoutParUrl() {
  const [nom, setNom] = useState("");
  const [url, setUrl] = useState("");
  const ajouter = useAddCompany();
  return (
    <form
      aria-label="Ajouter par adresse carrières"
      onSubmit={(e) => {
        e.preventDefault();
        ajouter.mutate(
          { name: nom.trim(), careers_url: url.trim(), enabled: true },
          {
            onSuccess: () => {
              toast.success("Entreprise ajoutée.");
              setNom("");
              setUrl("");
            },
            onError: (e2) => toast.error(e2.message),
          },
        );
      }}
      className="flex flex-wrap items-end gap-3"
    >
      <div className="min-w-48 flex-1">
        <Field label="Nom">
          {(champ) => <Input {...champ} value={nom} onChange={(e) => setNom(e.target.value)} />}
        </Field>
      </div>
      <div className="min-w-64 flex-[2]">
        <Field
          label="Adresse de la page carrières"
          hint="Greenhouse ou Lever, ex. https://boards.greenhouse.io/entreprise"
        >
          {(champ) => (
            <Input
              {...champ}
              type="url"
              value={url}
              placeholder="https://"
              onChange={(e) => setUrl(e.target.value)}
            />
          )}
        </Field>
      </div>
      <Button
        type="submit"
        variant="secondary"
        loading={ajouter.isPending}
        disabled={nom.trim() === "" || url.trim() === ""}
      >
        Ajouter
      </Button>
    </form>
  );
}

function etat(e: Company): {
  label: string;
  variant: "success" | "warning" | "danger" | "neutral";
} {
  if (e.detection_status === "unsupported") return { label: "Non supportée", variant: "danger" };
  if (e.detection_status === "pending") return { label: "Source non reconnue", variant: "warning" };
  if (!e.enabled) return { label: "Désactivée", variant: "neutral" };
  if (e.last_error) return { label: "Dernière collecte en échec", variant: "danger" };
  if (e.last_success_at) return { label: "Collectée", variant: "success" };
  return { label: "Jamais collectée", variant: "neutral" };
}

function Liste({ entreprises }: { entreprises: Company[] }) {
  const basculer = useSetCompanyEnabled();
  if (entreprises.length === 0) {
    return (
      <p className="text-sm text-foreground-muted">
        Aucune entreprise suivie. Cherchez-en une ci-dessus pour commencer.
      </p>
    );
  }
  return (
    <ul aria-label="Entreprises suivies" className="flex flex-col gap-2">
      {entreprises.map((e) => {
        const { label, variant } = etat(e);
        const supportee = e.detection_status === "supported";
        return (
          <li
            key={e.id}
            className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border px-3 py-2"
          >
            <div className="flex flex-col gap-1">
              <span className="text-sm font-medium text-foreground">{e.name}</span>
              <span className="text-xs text-foreground-muted">
                {e.ats_kind ? (ATS_LABELS[e.ats_kind] ?? e.ats_kind) : "Source inconnue"}
                {e.last_success_at
                  ? ` · dernière collecte réussie le ${new Date(e.last_success_at).toLocaleString("fr-FR")}`
                  : ""}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <Badge variant={variant}>{label}</Badge>
              <Button
                variant="ghost"
                disabled={!supportee || basculer.isPending}
                onClick={() =>
                  basculer.mutate(
                    { id: e.id, enabled: !e.enabled },
                    { onError: (err) => toast.error(err.message) },
                  )
                }
                aria-label={`${e.enabled ? "Désactiver" : "Activer"} ${e.name}`}
              >
                {e.enabled ? "Désactiver" : "Activer"}
              </Button>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function Bilan({ rapport }: { rapport: CollectionReport }) {
  return (
    <div role="status" className="flex flex-col gap-2 rounded-md border border-border p-3">
      <p className="text-sm font-medium text-foreground">{resumeCollecte(rapport)}</p>
      <ul aria-label="Sources interrogées" className="flex flex-col gap-1 text-sm">
        {rapport.sources.map((s) => (
          <li key={s.source_key} className="flex flex-wrap justify-between gap-2">
            <span className="text-foreground">{s.company_name}</span>
            <span className={s.succeeded ? "text-foreground-muted" : "text-danger"}>
              {s.succeeded
                ? `${pluriel(s.fetched, "offre")} lue${s.fetched > 1 ? "s" : ""} · ${s.created} nouvelle${s.created > 1 ? "s" : ""} · ${s.changed} mise${s.changed > 1 ? "s" : ""} à jour · ${s.expired} retirée${s.expired > 1 ? "s" : ""}`
                : "Source indisponible ou refusée : les autres sources ne sont pas affectées."}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function CompaniesPanel() {
  const entreprises = useCompanies();
  const collecter = useRunCollection();
  const aucuneActive = entreprises.isSuccess && !entreprises.data.some((e) => e.enabled);

  return (
    <Panel
      title="Entreprises suivies et collecte des offres"
      actions={
        <Button
          loading={collecter.isPending}
          disabled={entreprises.isPending || aucuneActive}
          title={aucuneActive ? "Activez au moins une entreprise." : undefined}
          onClick={() =>
            collecter.mutate(undefined, {
              onSuccess: (r) => toast.success(resumeCollecte(r)),
              onError: (e) => toast.error(e.message),
            })
          }
        >
          Collecter les offres
        </Button>
      }
    >
      <div className="flex flex-col gap-5">
        <p className="text-sm text-foreground-muted">
          Les offres viennent uniquement de sites carrières publics (API Greenhouse et Lever), à
          débit réduit et sans contournement. Aucune liste d&apos;entreprises n&apos;est imposée :
          cherchez celles qui vous intéressent.
        </p>
        <Recherche />
        {collecter.isSuccess ? <Bilan rapport={collecter.data} /> : null}
        {entreprises.isPending ? (
          <Skeleton className="h-24 w-full" />
        ) : entreprises.isError ? (
          <div className="flex flex-col items-start gap-3">
            <p role="alert" className="text-sm text-danger">
              {entreprises.error.message}
            </p>
            <Button variant="secondary" onClick={() => void entreprises.refetch()}>
              Réessayer
            </Button>
          </div>
        ) : (
          <Liste entreprises={entreprises.data} />
        )}
        <details className="text-sm">
          <summary className="cursor-pointer text-foreground-muted">
            Ajouter avec l&apos;adresse de la page carrières
          </summary>
          <div className="pt-3">
            <AjoutParUrl />
          </div>
        </details>
      </div>
    </Panel>
  );
}
