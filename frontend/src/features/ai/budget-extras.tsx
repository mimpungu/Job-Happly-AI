"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { toast } from "@/components/ui/toaster";
import type { AIAlert, AISettings } from "@/types/ai";

import { useEstimateAICost, useSaveProviderCap, useSaveTaskCap } from "./use-ai";

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

interface LignePlafond {
  cle: string;
  libelle: string;
}

/** Une ligne par entité plafonnée (fournisseur, tâche) : montant au centime, vide = pas de plafond. */
function ListePlafonds({
  lignes,
  plafonds,
  devise,
  nomFormulaire,
  enregistrer,
  enCours,
}: {
  lignes: LignePlafond[];
  plafonds: Record<string, string>;
  devise: string;
  nomFormulaire: (ligne: LignePlafond) => string;
  enregistrer: (cle: string, montant: string | null) => void;
  enCours: boolean;
}) {
  const [saisies, setSaisies] = useState<Record<string, string>>({});
  const valeur = (cle: string) => saisies[cle] ?? plafonds[cle] ?? "";
  const valide = (v: string) => v === "" || (/^\d+(\.\d{1,2})?$/.test(v) && Number(v) > 0);
  return (
    <div className="flex flex-col gap-4">
      {lignes.map((l) => (
        <form
          key={l.cle}
          aria-label={nomFormulaire(l)}
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            const v = valeur(l.cle).trim();
            enregistrer(l.cle, v === "" ? null : v);
          }}
        >
          <Field
            label={`${l.libelle} — plafond journalier (${devise})`}
            hint="Vide : seulement les plafonds globaux."
            error={valide(valeur(l.cle)) ? undefined : "Montant positif, 2 décimales au plus."}
          >
            {(champ) => (
              <Input
                {...champ}
                inputMode="decimal"
                value={valeur(l.cle)}
                onChange={(e) => setSaisies({ ...saisies, [l.cle]: e.target.value })}
              />
            )}
          </Field>
          <Button
            type="submit"
            variant="secondary"
            loading={enCours}
            disabled={!valide(valeur(l.cle))}
          >
            Enregistrer
          </Button>
        </form>
      ))}
    </div>
  );
}

/** Plafond journalier propre à chaque fournisseur payant, en plus des plafonds globaux. */
export function PlafondsFournisseurs({ reglages }: { reglages: AISettings }) {
  const payants = reglages.providers.filter((p) => p.kind === "api");
  const ecrire = useSaveProviderCap();
  if (payants.length === 0) {
    return (
      <p className="text-sm text-foreground-muted">
        Aucune API payante configurée : il n&apos;y a pas de plafond par fournisseur à régler.
      </p>
    );
  }
  return (
    <ListePlafonds
      lignes={payants.map((p) => ({ cle: p.name, libelle: p.name }))}
      plafonds={reglages.provider_daily_caps}
      devise={reglages.currency}
      nomFormulaire={(l) => `Plafond de ${l.libelle}`}
      enCours={ecrire.isPending}
      enregistrer={(provider, daily) =>
        ecrire.mutate(
          { provider, daily },
          {
            onSuccess: () => toast.success(`Plafond de ${provider} enregistré.`),
            onError: (erreur) => toast.error(erreur.message),
          },
        )
      }
    />
  );
}

/** Plafond journalier propre à chaque tâche IA : borne, par exemple, la reformulation du CV. */
export function PlafondsParTache({ reglages }: { reglages: AISettings }) {
  const ecrire = useSaveTaskCap();
  return (
    <ListePlafonds
      lignes={reglages.tasks.map((t) => ({ cle: t.task_type, libelle: t.label }))}
      plafonds={reglages.task_daily_caps}
      devise={reglages.currency}
      nomFormulaire={(l) => `Plafond de la tâche ${l.libelle}`}
      enCours={ecrire.isPending}
      enregistrer={(task, daily) =>
        ecrire.mutate(
          { task, daily },
          {
            onSuccess: () => toast.success("Plafond de la tâche enregistré."),
            onError: (erreur) => toast.error(erreur.message),
          },
        )
      }
    />
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
