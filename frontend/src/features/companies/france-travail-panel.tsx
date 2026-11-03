"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "@/components/ui/toaster";
import type { FranceTravailResult } from "@/types/companies";

import { useFranceTravailSearch, useFranceTravailStatus } from "./use-companies";

const ERREURS: Record<string, string> = {
  AuthenticationFailedError: "France Travail a refusé les identifiants. Vérifiez-les dans .env.",
  NotConfiguredError: "France Travail n'est pas configuré.",
  RateLimitedError: "Quota France Travail atteint : réessayez plus tard.",
};

/** Résumé : un échec est nommé, jamais présenté comme « 0 offre ». */
export function resumeRecherche(r: FranceTravailResult): string {
  if (!r.succeeded) {
    return ERREURS[r.error_type ?? ""] ?? "La recherche France Travail a échoué.";
  }
  return `${r.fetched} offre${r.fetched > 1 ? "s" : ""} lue${r.fetched > 1 ? "s" : ""} · ${r.created} nouvelle${r.created > 1 ? "s" : ""}`;
}

function Formulaire() {
  const [intitule, setIntitule] = useState("");
  const [entreprise, setEntreprise] = useState("");
  const [ville, setVille] = useState("");
  const [departement, setDepartement] = useState("");
  const recherche = useFranceTravailSearch();

  const departementValide = departement === "" || /^(\d{2}|2[AB]|97\d)$/.test(departement);
  const complet = intitule.trim() !== "" || entreprise.trim() !== "";

  return (
    <div className="flex flex-col gap-3">
      <form
        aria-label="Recherche France Travail"
        onSubmit={(e) => {
          e.preventDefault();
          recherche.mutate(
            {
              title: intitule.trim() || null,
              company: entreprise.trim() || null,
              keywords: [],
              city: ville.trim() || null,
              department: departement || null,
            },
            {
              onSuccess: (r) =>
                r.succeeded ? toast.success(resumeRecherche(r)) : toast.error(resumeRecherche(r)),
              onError: (err) => toast.error(err.message),
            },
          );
        }}
        className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"
      >
        <Field label="Intitulé ou domaine" hint="Ex. développeur, informatique">
          {(champ) => (
            <Input {...champ} value={intitule} onChange={(e) => setIntitule(e.target.value)} />
          )}
        </Field>
        <Field label="Entreprise" hint="Ex. BNP Paribas">
          {(champ) => (
            <Input {...champ} value={entreprise} onChange={(e) => setEntreprise(e.target.value)} />
          )}
        </Field>
        <Field label="Ville" hint="Affine les résultats reçus">
          {(champ) => <Input {...champ} value={ville} onChange={(e) => setVille(e.target.value)} />}
        </Field>
        <Field
          label="Département"
          hint="Ex. 75 pour Paris : restreint la recherche à la source"
          error={departementValide ? undefined : "Code de département invalide."}
        >
          {(champ) => (
            <Input
              {...champ}
              value={departement}
              maxLength={3}
              onChange={(e) => setDepartement(e.target.value.toUpperCase())}
            />
          )}
        </Field>
        <div className="sm:col-span-2 lg:col-span-4">
          <Button
            type="submit"
            loading={recherche.isPending}
            disabled={!complet || !departementValide}
          >
            Rechercher sur France Travail
          </Button>
        </div>
      </form>
      {recherche.isSuccess ? (
        <p role="status" className="text-sm text-foreground">
          {resumeRecherche(recherche.data)} Retrouvez-les dans la recherche d&apos;offres.
        </p>
      ) : null}
    </div>
  );
}

export function FranceTravailPanel() {
  const statut = useFranceTravailStatus();
  return (
    <Panel title="France Travail (API officielle)">
      <div className="flex flex-col gap-4">
        <p className="text-sm text-foreground-muted">
          Source officielle qui couvre les grands employeurs sans site Greenhouse ou Lever. Aucune
          candidature n&apos;est envoyée.
        </p>
        {statut.isPending ? (
          <Skeleton className="h-16 w-full" />
        ) : statut.isError ? (
          <p role="alert" className="text-sm text-danger">
            {statut.error.message}
          </p>
        ) : statut.data.configured ? (
          <Formulaire />
        ) : (
          <div role="status" className="flex flex-col gap-2 text-sm text-foreground-muted">
            <p className="font-medium text-foreground">Non configuré</p>
            <p>
              France Travail a retiré l&apos;API « Offres d&apos;emploi » de son portail le temps
              d&apos;analyser les conditions de réutilisation. Les organismes qui en ont besoin
              doivent en faire la demande via le formulaire de contact de francetravail.io.
            </p>
            <p>
              Si l&apos;accès vous est accordé, renseignez HAPPLY_FRANCE_TRAVAIL_CLIENT_ID et
              HAPPLY_FRANCE_TRAVAIL_CLIENT_SECRET dans le fichier .env, puis redémarrez l&apos;API.
            </p>
          </div>
        )}
      </div>
    </Panel>
  );
}
