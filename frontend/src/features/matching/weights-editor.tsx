"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import { Panel } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "@/components/ui/toaster";
import type { WeightsResponse } from "@/types/matching";

import { CRITERION_LABELS } from "./labels";
import { useRecompute, useResetWeights, useSaveWeights, useWeights } from "./use-matching";

/** Poids valide : nombre entre 0 et 100. Vide ou non numérique = invalide (jamais « 0 » implicite). */
export function poidsValide(valeur: string): boolean {
  if (valeur.trim() === "") return false;
  const nombre = Number(valeur);
  return Number.isFinite(nombre) && nombre >= 0 && nombre <= 100;
}

function depuis(vue: WeightsResponse): Record<string, string> {
  return Object.fromEntries(vue.criteria.map((c) => [c.key, String(Number(c.weight))]));
}

function Formulaire({ vue }: { vue: WeightsResponse }) {
  const [valeurs, setValeurs] = useState(() => depuis(vue));
  const enregistrer = useSaveWeights();
  const reinitialiser = useResetWeights();
  const recalculer = useRecompute();

  const invalides = vue.criteria.filter((c) => !poidsValide(valeurs[c.key] ?? ""));
  const nombres = vue.criteria.map((c) =>
    poidsValide(valeurs[c.key] ?? "") ? Number(valeurs[c.key]) : 0,
  );
  const total = nombres.reduce((a, b) => a + b, 0);
  const aucunActif = invalides.length === 0 && total <= 0;
  const initial = depuis(vue);
  const modifie = vue.criteria.some((c) => (valeurs[c.key] ?? "") !== initial[c.key]);
  const erreurFormulaire = invalides.length > 0 || aucunActif;

  const sauvegarder = () =>
    enregistrer.mutate(
      Object.fromEntries(vue.criteria.map((c) => [c.key, Number(valeurs[c.key])])),
      {
        onSuccess: () =>
          toast.success(
            "Pondérations enregistrées. Recalculez les scores pour les appliquer aux offres.",
          ),
        onError: (e) => toast.error(e.message),
      },
    );

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-foreground-muted">
        Réglez l&apos;importance de chaque critère dans le score de compatibilité. Seuls les
        rapports entre poids comptent. Un poids à 0 désactive le critère. Les critères dont les
        données manquent ne sont jamais comptés comme un échec.
      </p>
      <form
        aria-label="Pondérations du score"
        onSubmit={(e) => {
          e.preventDefault();
          if (!erreurFormulaire && modifie) sauvegarder();
        }}
        className="flex flex-col gap-4"
      >
        <div className="grid gap-4 sm:grid-cols-2">
          {vue.criteria.map((c) => {
            const valeur = valeurs[c.key] ?? "";
            const valide = poidsValide(valeur);
            const part = valide && total > 0 ? Math.round((Number(valeur) / total) * 100) : 0;
            return (
              <Field
                key={c.key}
                label={CRITERION_LABELS[c.key]}
                hint={`Par défaut : ${Number(c.default_weight)}${valide ? ` · part actuelle : ${part} %` : ""}`}
                error={valide ? undefined : "Saisissez un nombre entre 0 et 100."}
              >
                {(champ) => (
                  <Input
                    {...champ}
                    type="number"
                    min={0}
                    max={100}
                    step="any"
                    inputMode="decimal"
                    value={valeur}
                    onChange={(e) => setValeurs((v) => ({ ...v, [c.key]: e.target.value }))}
                  />
                )}
              </Field>
            );
          })}
        </div>
        {aucunActif ? (
          <p role="alert" className="text-sm text-danger">
            Au moins un critère doit avoir un poids supérieur à 0.
          </p>
        ) : null}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-foreground-muted">
            {vue.is_default ? "Pondérations par défaut" : "Pondérations personnalisées"} · version{" "}
            {vue.version}
          </p>
          <div className="flex flex-wrap gap-3">
            <Button
              variant="ghost"
              loading={reinitialiser.isPending}
              disabled={vue.is_default && !modifie}
              onClick={() =>
                reinitialiser.mutate(undefined, {
                  onSuccess: (nouvelle) => {
                    setValeurs(depuis(nouvelle));
                    toast.success("Pondérations par défaut rétablies.");
                  },
                  onError: (e) => toast.error(e.message),
                })
              }
            >
              Rétablir les valeurs par défaut
            </Button>
            <Button
              type="submit"
              loading={enregistrer.isPending}
              disabled={erreurFormulaire || !modifie}
            >
              Enregistrer
            </Button>
          </div>
        </div>
      </form>
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
        <p className="max-w-prose text-sm text-foreground-muted">
          Les scores des offres se calculent avec votre profil validé et ces pondérations. Après un
          changement, recalculez-les pour mettre à jour le tri et les filtres.
        </p>
        <Button
          variant="secondary"
          loading={recalculer.isPending}
          disabled={modifie}
          title={modifie ? "Enregistrez d'abord vos pondérations." : undefined}
          onClick={() =>
            recalculer.mutate(undefined, {
              onSuccess: (r) =>
                toast.success(
                  `${r.computed} offre${r.computed > 1 ? "s" : ""} évaluée${r.computed > 1 ? "s" : ""}${
                    r.not_computable > 0 ? ` · ${r.not_computable} sans donnée suffisante` : ""
                  }.`,
                ),
              onError: (e) => toast.error(e.message),
            })
          }
        >
          Recalculer les scores
        </Button>
      </div>
    </div>
  );
}

export function WeightsEditor() {
  const poids = useWeights();
  return (
    <Panel title="Pondérations du score de compatibilité">
      {poids.isPending ? (
        <Skeleton className="h-48 w-full" />
      ) : poids.isError ? (
        <div className="flex flex-col items-start gap-3">
          <p role="alert" className="text-sm text-danger">
            {poids.error.message}
          </p>
          <Button variant="secondary" onClick={() => void poids.refetch()}>
            Réessayer
          </Button>
        </div>
      ) : (
        // La clé réinitialise le formulaire quand le serveur renvoie de nouvelles pondérations.
        <Formulaire key={poids.data.version} vue={poids.data} />
      )}
    </Panel>
  );
}
