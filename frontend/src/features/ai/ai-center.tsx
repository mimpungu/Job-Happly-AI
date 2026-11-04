"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "@/components/ui/toaster";
import type { SelectOption } from "@/components/ui/select";
import type { AIMode, AIProviderView, AISettings, AIUsage, BackendPreference } from "@/types/ai";

import {
  useAISettings,
  useAITest,
  useAIUsage,
  useSaveAIBudget,
  useSaveAIConsent,
  useSaveAISettings,
} from "./use-ai";

export const MODES = [
  { value: "disabled", label: "IA désactivée" },
  { value: "economy", label: "Économique" },
  { value: "balanced", label: "Équilibré" },
  { value: "quality", label: "Qualité" },
] as const;

const NOMS: Record<string, string> = { ollama: "Ollama", gemini: "Gemini" };
const nomAffiche = (p: AIProviderView) => NOMS[p.name] ?? p.name;

/**
 * Choix de l'IA présenté à l'utilisateur : un fournisseur par nom, plus l'automatique.
 * Un fournisseur non configuré reste visible (on voit ce qui manque) mais non sélectionnable.
 * Chaque choix correspond à une préférence du serveur (local seul, API seule, hybride).
 */
export function choixIA(providers: AIProviderView[]): SelectOption[] {
  const local = providers.find((p) => p.kind === "local");
  const api = providers.find((p) => p.kind === "api");
  return [
    {
      value: "hybrid",
      label:
        local && api
          ? `Automatique : ${nomAffiche(local)} d'abord, ${nomAffiche(api)} en renfort`
          : "Automatique (nécessite Ollama et Gemini)",
      disabled: !(local && api),
    },
    {
      value: "local_only",
      label: local
        ? `${nomAffiche(local)} — local, gratuit, rien ne quitte votre machine`
        : "Ollama — non configuré",
      disabled: !local,
    },
    {
      value: "api_only",
      label: api
        ? `${nomAffiche(api)} — ${api.uses_data_for_training ? "palier gratuit, textes publics seulement" : "API payante, sous plafond"}`
        : "Gemini — non configuré (clé absente)",
      disabled: !api,
    },
  ];
}

/** Vrai si le choix enregistré désigne une IA aujourd'hui indisponible. */
export function choixIndisponible(reglages: AISettings): boolean {
  // Sans aucun fournisseur, le panneau « État » l'explique déjà : pas de seconde alerte.
  if (reglages.providers.length === 0) return false;
  const option = choixIA(reglages.providers).find((o) => o.value === reglages.backend_preference);
  return option?.disabled ?? true;
}

/** Montant décimal positif avec au plus 2 décimales (aligné sur la contrainte serveur). */
export function montantValide(valeur: string): boolean {
  return /^\d{1,4}(\.\d{1,2})?$/.test(valeur.trim()) && Number(valeur) > 0;
}

const argent = (valeur: string, devise: string) =>
  `${Number(valeur).toLocaleString("fr-FR", { maximumFractionDigits: 4 })} ${devise}`;

function Etat({ reglages }: { reglages: AISettings }) {
  const locaux = reglages.providers.filter((p) => p.kind === "local");
  const api = reglages.providers.filter((p) => p.kind === "api");
  return (
    <div className="flex flex-col gap-2 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={reglages.mode === "disabled" ? "neutral" : "accent"}>
          {MODES.find((m) => m.value === reglages.mode)?.label}
        </Badge>
        <Badge variant={locaux.length > 0 ? "success" : "neutral"}>
          {locaux.length > 0 ? "Modèle local disponible" : "Aucun modèle local"}
        </Badge>
        <Badge variant={reglages.paid_calls_possible ? "warning" : "neutral"}>
          {reglages.paid_calls_possible ? "API payante autorisée" : "Aucun appel payant possible"}
        </Badge>
      </div>
      {reglages.providers.some((p) => p.uses_data_for_training) ? (
        <p role="note" className="rounded-md border border-warning p-3 text-foreground">
          <strong>Palier gratuit détecté.</strong> Le fournisseur peut réutiliser et faire relire
          les contenus envoyés. Ne l&apos;utilisez que pour des textes publics (offres
          d&apos;emploi), jamais pour votre CV ni votre profil : l&apos;application les exclut
          automatiquement de ce fournisseur.
        </p>
      ) : null}
      {reglages.providers.length === 0 ? (
        <p className="text-foreground-muted">
          Aucun fournisseur d&apos;IA n&apos;est branché pour l&apos;instant : l&apos;application
          fonctionne entièrement sans IA (règles et scores déterministes). Le choix du fournisseur
          payant fait l&apos;objet d&apos;une décision d&apos;architecture à venir.
        </p>
      ) : (
        <p className="text-foreground-muted">
          Fournisseurs :{" "}
          {[...locaux, ...api]
            .map((p) => `${p.name} (${p.kind})${p.key_hint ? `, clé ${p.key_hint}` : ""}`)
            .join(", ")}
          . La clé n&apos;est jamais affichée : seule sa fin l&apos;est, pour vérifier une rotation.
        </p>
      )}
    </div>
  );
}

function ModeEtPreference({ reglages }: { reglages: AISettings }) {
  const enregistrer = useSaveAISettings();
  const modifier = (corps: { mode?: AIMode; backend_preference?: BackendPreference }) =>
    enregistrer.mutate(corps, {
      onSuccess: () => toast.success("Réglage enregistré."),
      onError: (e) => toast.error(e.message),
    });
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Field
        label="Mode"
        hint="Économique : modèle le moins cher suffisant. Qualité : modèle le plus performant."
      >
        {(c) => (
          <Select
            {...c}
            options={MODES}
            value={reglages.mode}
            onChange={(e) => modifier({ mode: e.target.value as AIMode })}
          />
        )}
      </Field>
      <Field
        label="IA utilisée"
        hint="Choisissez Ollama (local), Gemini ou l'automatique. En automatique, le local passe en premier."
        error={
          choixIndisponible(reglages)
            ? "L'IA choisie n'est pas configurée : les appels IA seront refusés."
            : undefined
        }
      >
        {(c) => (
          <Select
            {...c}
            options={choixIA(reglages.providers)}
            value={reglages.backend_preference}
            onChange={(e) => modifier({ backend_preference: e.target.value as BackendPreference })}
          />
        )}
      </Field>
    </div>
  );
}

function Plafonds({ reglages }: { reglages: AISettings }) {
  const [jour, setJour] = useState(
    reglages.daily_budget ? String(Number(reglages.daily_budget)) : "",
  );
  const [mois, setMois] = useState(
    reglages.monthly_budget ? String(Number(reglages.monthly_budget)) : "",
  );
  const enregistrer = useSaveAIBudget();
  const valide = montantValide(jour) && montantValide(mois) && Number(jour) <= Number(mois);
  return (
    <form
      aria-label="Plafonds de dépense"
      onSubmit={(e) => {
        e.preventDefault();
        if (!valide) return;
        enregistrer.mutate(
          { daily: jour.trim(), monthly: mois.trim(), currency: reglages.currency },
          {
            onSuccess: () => toast.success("Plafonds enregistrés."),
            onError: (err) => toast.error(err.message),
          },
        );
      }}
      className="flex flex-col gap-3"
    >
      <p className="text-sm text-foreground-muted">
        Aucun appel payant n&apos;est possible tant que les deux plafonds ne sont pas définis.
        L&apos;application n&apos;augmente jamais un plafond d&apos;elle-même et refuse tout appel
        qui le ferait dépasser. Limite par opération :{" "}
        {argent(reglages.per_operation_level1, reglages.currency)} (niveau 1),{" "}
        {argent(reglages.per_operation_level2, reglages.currency)} (niveau 2).
      </p>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field
          label={`Plafond journalier (${reglages.currency})`}
          error={
            jour === "" || montantValide(jour) ? undefined : "Montant positif, 2 décimales au plus."
          }
        >
          {(c) => (
            <Input
              {...c}
              inputMode="decimal"
              value={jour}
              onChange={(e) => setJour(e.target.value)}
            />
          )}
        </Field>
        <Field
          label={`Plafond mensuel (${reglages.currency})`}
          error={
            mois === "" || montantValide(mois) ? undefined : "Montant positif, 2 décimales au plus."
          }
        >
          {(c) => (
            <Input
              {...c}
              inputMode="decimal"
              value={mois}
              onChange={(e) => setMois(e.target.value)}
            />
          )}
        </Field>
      </div>
      {montantValide(jour) && montantValide(mois) && Number(jour) > Number(mois) ? (
        <p role="alert" className="text-sm text-danger">
          Le plafond journalier ne peut pas dépasser le plafond mensuel.
        </p>
      ) : null}
      <div>
        <Button type="submit" loading={enregistrer.isPending} disabled={!valide}>
          Enregistrer les plafonds
        </Button>
      </div>
    </form>
  );
}

function Consentement({ reglages }: { reglages: AISettings }) {
  const consentir = useSaveAIConsent();
  return (
    <div className="flex flex-col gap-3 text-sm">
      <p className="text-foreground-muted">
        Une API payante reçoit uniquement le texte nécessaire à la tâche (par exemple le texte
        d&apos;une offre). Votre CV complet n&apos;est jamais envoyé par défaut, et aucune
        candidature n&apos;est envoyée automatiquement. Un modèle local ne fait rien sortir de votre
        machine et n&apos;a pas besoin de cet accord.
      </p>
      <div className="flex flex-wrap items-center gap-3">
        <Badge variant={reglages.api_consent ? "success" : "neutral"}>
          {reglages.api_consent ? "Envoi à l'API accepté" : "Envoi à l'API non accepté"}
        </Badge>
        <Button
          variant={reglages.api_consent ? "ghost" : "secondary"}
          loading={consentir.isPending}
          onClick={() =>
            consentir.mutate(!reglages.api_consent, {
              onError: (e) => toast.error(e.message),
            })
          }
        >
          {reglages.api_consent ? "Retirer mon accord" : "J'accepte l'envoi de ces données"}
        </Button>
      </div>
    </div>
  );
}

function Jauge({
  libelle,
  pourcent,
  depense,
  plafond,
  devise,
}: {
  libelle: string;
  pourcent: string | null;
  depense: string;
  plafond: string | null;
  devise: string;
}) {
  const valeur = pourcent === null ? null : Math.min(100, Number(pourcent));
  return (
    <div className="flex flex-col gap-1">
      <div className="flex flex-wrap justify-between gap-2 text-sm">
        <span className="text-foreground">{libelle}</span>
        <span className="text-foreground-muted">
          {argent(depense, devise)}
          {plafond ? ` sur ${argent(plafond, devise)}` : " · plafond non défini"}
        </span>
      </div>
      {valeur !== null ? (
        <div
          role="meter"
          aria-label={libelle}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={valeur}
          aria-valuetext={`${valeur} % du plafond`}
          className="h-2 overflow-hidden rounded-full bg-background-tertiary"
        >
          <div className="h-full bg-accent" style={{ width: `${valeur}%` }} />
        </div>
      ) : null}
    </div>
  );
}

const ISSUES: Record<string, string> = {
  success: "Réussi",
  cache_hit: "Cache (gratuit)",
  blocked_budget: "Bloqué (plafond)",
  error: "Erreur du fournisseur",
  invalid_output: "Sortie invalide",
};

function Consommation({ usage }: { usage: AIUsage }) {
  return (
    <div className="flex flex-col gap-4">
      <Jauge
        libelle="Aujourd'hui"
        pourcent={usage.percent_today}
        depense={usage.spent_today}
        plafond={usage.daily_budget}
        devise={usage.currency}
      />
      <Jauge
        libelle="Ce mois-ci"
        pourcent={usage.percent_month}
        depense={usage.spent_month}
        plafond={usage.monthly_budget}
        devise={usage.currency}
      />
      {usage.recent.length === 0 ? (
        <p className="text-sm text-foreground-muted">
          Aucun appel IA enregistré. Les appels refusés ou servis par le cache apparaîtront aussi
          ici.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Derniers appels IA</caption>
            <thead className="text-foreground-muted">
              <tr>
                <th scope="col" className="py-1 pr-3">
                  Date
                </th>
                <th scope="col" className="py-1 pr-3">
                  Tâche
                </th>
                <th scope="col" className="py-1 pr-3">
                  Fournisseur
                </th>
                <th scope="col" className="py-1 pr-3">
                  Résultat
                </th>
                <th scope="col" className="py-1 text-right">
                  Coût
                </th>
              </tr>
            </thead>
            <tbody>
              {usage.recent.map((l, i) => (
                <tr key={`${l.at}-${i}`} className="border-t border-border">
                  <td className="py-1 pr-3">{new Date(l.at).toLocaleString("fr-FR")}</td>
                  <td className="py-1 pr-3">{l.task_type}</td>
                  <td className="py-1 pr-3">{l.provider}</td>
                  <td className="py-1 pr-3">{ISSUES[l.outcome] ?? l.outcome}</td>
                  <td className="py-1 text-right">{argent(l.cost, l.currency)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Chargement<T>({
  requete,
  children,
}: {
  requete: {
    isPending: boolean;
    isError: boolean;
    error: Error | null;
    data: T | undefined;
    refetch: () => unknown;
  };
  children: (donnees: T) => React.ReactNode;
}) {
  if (requete.isPending) return <Skeleton className="h-24 w-full" />;
  if (requete.isError || requete.data === undefined)
    return (
      <div className="flex flex-col items-start gap-3">
        <p role="alert" className="text-sm text-danger">
          {requete.error?.message ?? "Chargement impossible."}
        </p>
        <Button variant="secondary" onClick={() => void requete.refetch()}>
          Réessayer
        </Button>
      </div>
    );
  return <>{children(requete.data)}</>;
}

function Test() {
  const test = useAITest();
  return (
    <div className="flex flex-col gap-3 text-sm">
      <p className="text-foreground-muted">
        Envoie un court texte d&apos;offre fictif et public (aucune donnée personnelle) à travers
        toute la chaîne : routage, accord, plafonds, appel, validation, journal et cache. Relancer
        le test doit afficher « cache » et un coût nul.
      </p>
      <div className="flex flex-wrap gap-3">
        {([1, 2] as const).map((niveau) => (
          <Button
            key={niveau}
            variant="secondary"
            loading={test.isPending && test.variables === niveau}
            disabled={test.isPending}
            onClick={() => test.mutate(niveau)}
          >
            {niveau === 1 ? "Tester l'IA (niveau 1, économique)" : "Tester l'IA (niveau 2)"}
          </Button>
        ))}
      </div>
      {test.isError ? (
        <p role="alert" className="text-danger">
          {test.error.message}
        </p>
      ) : null}
      {test.isSuccess ? (
        <div role="status" className="flex flex-col gap-1 rounded-md border border-border p-3">
          <p className="font-medium text-foreground">
            {test.data.provider} · {test.data.model}
            {test.data.cache_hit ? " · servi par le cache" : ""}
          </p>
          <p className="text-foreground-muted">
            {test.data.input_tokens} tokens en entrée, {test.data.output_tokens} en sortie · coût{" "}
            {Number(test.data.cost).toLocaleString("fr-FR", { maximumFractionDigits: 6 })}
          </p>
          <p className="text-foreground">{test.data.summary}</p>
          <p className="text-foreground-muted">
            Compétences : {test.data.skills.join(", ") || "—"}
          </p>
          {test.data.crossed_thresholds.length > 0 ? (
            <p className="text-warning">
              Seuil d&apos;alerte franchi : {test.data.crossed_thresholds.join(" %, ")} %.
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function AICenter() {
  const reglages = useAISettings();
  const usage = useAIUsage();
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold text-foreground">Centre IA</h1>
      <Panel title="État">
        <Chargement requete={reglages}>{(r) => <Etat reglages={r} />}</Chargement>
      </Panel>
      <Panel title="Mode et exécution">
        <Chargement requete={reglages}>{(r) => <ModeEtPreference reglages={r} />}</Chargement>
      </Panel>
      <Panel title="Plafonds de dépense">
        <Chargement requete={reglages}>
          {(r) => <Plafonds key={`${r.daily_budget}-${r.monthly_budget}`} reglages={r} />}
        </Chargement>
      </Panel>
      <Panel title="Données transmises à une API payante">
        <Chargement requete={reglages}>{(r) => <Consentement reglages={r} />}</Chargement>
      </Panel>
      <Panel title="Tester la plateforme">
        <Test />
      </Panel>
      <Panel title="Consommation">
        <Chargement requete={usage}>{(u) => <Consommation usage={u} />}</Chargement>
      </Panel>
    </div>
  );
}
