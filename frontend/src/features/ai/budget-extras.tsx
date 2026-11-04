"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { toast } from "@/components/ui/toaster";
import type { AIAlert, AISettings } from "@/types/ai";

import { useEstimateAICost, useSaveProviderCap } from "./use-ai";

const PERIODES: Record<AIAlert["period"], string> = {
  daily: "journalier",
  monthly: "mensuel",
};

/** Alertes de seuil : visibles tant que le seuil est franchi, sans action de l'utilisateur. */
export function AlertesBudget({ alertes, devise }: { alertes: AIAlert[]; devise: string }) {
  if (alertes.length === 0) return null;
  return (
    <ul aria-label="Alertes de budget" className="flex flex-col gap-2">
      {alertes.map((a) => (
        <li key={a.period} role="status" className="flex flex-wrap items-center gap-2 text-sm">
          <Badge variant={a.threshold >= 100 ? "danger" : "warning"}>Seuil {a.threshold} %</Badge>
          <span>
            Plafond {PERIODES[a.period]} utilisé à {a.percent} % ({a.spent} / {a.limit} {devise}).
            {a.threshold >= 100
              ? " Les appels payants sont bloqués jusqu'à la prochaine période."
              : ""}
          </span>
        </li>
      ))}
    </ul>
  );
}

/** Plafond journalier propre à chaque fournisseur payant, en plus des plafonds globaux. */
export function PlafondsFournisseurs({ reglages }: { reglages: AISettings }) {
  const payants = reglages.providers.filter((p) => p.kind === "api");
  const ecrire = useSaveProviderCap();
  const [saisies, setSaisies] = useState<Record<string, string>>({});
  if (payants.length === 0) {
    return (
      <p className="text-sm text-foreground-muted">
        Aucune API payante configurée : il n&apos;y a pas de plafond par fournisseur à régler.
      </p>
    );
  }
  const valeur = (nom: string) => saisies[nom] ?? reglages.provider_daily_caps[nom] ?? "";
  const valide = (v: string) => v === "" || (/^\d+(\.\d{1,2})?$/.test(v) && Number(v) > 0);
  return (
    <div className="flex flex-col gap-4">
      {payants.map((p) => (
        <form
          key={p.name}
          aria-label={`Plafond de ${p.name}`}
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            const v = valeur(p.name).trim();
            ecrire.mutate(
              { provider: p.name, daily: v === "" ? null : v },
              {
                onSuccess: () => toast.success(`Plafond de ${p.name} enregistré.`),
                onError: (erreur) => toast.error(erreur.message),
              },
            );
          }}
        >
          <Field
            label={`${p.name} — plafond journalier (${reglages.currency})`}
            hint="Vide : seulement les plafonds globaux."
            error={valide(valeur(p.name)) ? undefined : "Montant positif, 2 décimales au plus."}
          >
            {(champ) => (
              <Input
                {...champ}
                inputMode="decimal"
                value={valeur(p.name)}
                onChange={(e) => setSaisies({ ...saisies, [p.name]: e.target.value })}
              />
            )}
          </Field>
          <Button
            type="submit"
            variant="secondary"
            loading={ecrire.isPending}
            disabled={!valide(valeur(p.name))}
          >
            Enregistrer
          </Button>
        </form>
      ))}
    </div>
  );
}

const NIVEAUX = [
  { value: "1", label: "Niveau 1 (tâche légère)" },
  { value: "2", label: "Niveau 2 (tâche complexe)" },
] as const;

/** Coût maximal d'une opération avant de la lancer ; n'appelle aucun modèle. */
export function EstimationCout() {
  const estimer = useEstimateAICost();
  const [caracteres, setCaracteres] = useState("3000");
  const [niveau, setNiveau] = useState<"1" | "2">("1");
  const n = Number(caracteres);
  const valide = Number.isInteger(n) && n >= 0 && n <= 200_000;
  const resultat = estimer.data;
  return (
    <div className="flex flex-col gap-3">
      <form
        aria-label="Estimer un coût"
        className="flex flex-wrap items-end gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          estimer.mutate(
            { characters: n, level: niveau === "1" ? 1 : 2 },
            { onError: (erreur) => toast.error(erreur.message) },
          );
        }}
      >
        <Field
          label="Taille du texte (caractères)"
          error={valide ? undefined : "Entier de 0 à 200 000."}
        >
          {(champ) => (
            <Input
              {...champ}
              inputMode="numeric"
              value={caracteres}
              onChange={(e) => setCaracteres(e.target.value)}
            />
          )}
        </Field>
        <Field label="Complexité">
          {({ id }) => (
            <Select
              id={id}
              options={NIVEAUX}
              value={niveau}
              onChange={(e) => setNiveau(e.target.value === "2" ? "2" : "1")}
            />
          )}
        </Field>
        <Button type="submit" variant="secondary" loading={estimer.isPending} disabled={!valide}>
          Estimer
        </Button>
      </form>
      {resultat ? (
        <p role="status" className="text-sm">
          {resultat.paid
            ? `Coût maximal : ${resultat.cost} ${resultat.currency} (${resultat.provider}, ${resultat.model}).`
            : `Gratuit : exécuté en local (${resultat.provider}).`}{" "}
          {resultat.allowed ? null : <strong>Refusé aujourd&apos;hui : {resultat.reason}</strong>}
        </p>
      ) : null}
    </div>
  );
}
