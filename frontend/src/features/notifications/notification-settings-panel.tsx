"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "@/components/ui/toaster";
import { getNotificationPreferences, saveNotificationPreferences } from "@/services/notifications";
import type { NotificationPreferences } from "@/types/notifications";

const CLE = ["notifications", "preferences"] as const;

type Evenement =
  | "notify_new_offers"
  | "notify_relevant_matches"
  | "notify_search_errors"
  | "notify_follow_up_reminders"
  | "notify_ai_budget_alerts";

const EVENEMENTS: { cle: Evenement; libelle: string }[] = [
  { cle: "notify_new_offers", libelle: "Nouvelles offres collectées" },
  { cle: "notify_relevant_matches", libelle: "Offres très compatibles avec mon profil" },
  { cle: "notify_search_errors", libelle: "Erreurs de collecte ou de source" },
  { cle: "notify_follow_up_reminders", libelle: "Relances de candidature à faire" },
  { cle: "notify_ai_budget_alerts", libelle: "Seuils du budget IA atteints" },
];

function Case({
  libelle,
  coche,
  onChange,
  disabled,
}: {
  libelle: string;
  coche: boolean;
  onChange: (valeur: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <label className="flex items-center gap-2 text-sm text-foreground">
      <input
        type="checkbox"
        checked={coche}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      {libelle}
    </label>
  );
}

function Formulaire({ initial }: { initial: NotificationPreferences }) {
  const client = useQueryClient();
  const enregistrer = useMutation({
    mutationFn: saveNotificationPreferences,
    onSuccess: (vue) => client.setQueryData(CLE, vue),
  });
  const [p, setP] = useState(initial);
  const maj = <K extends keyof NotificationPreferences>(
    cle: K,
    valeur: NotificationPreferences[K],
  ) => setP((courant) => ({ ...courant, [cle]: valeur }));

  const emailValide =
    !p.email_enabled || (p.email_consent_given && (p.email_recipient ?? "").includes("@"));
  const soumettre = (evenement: FormEvent) => {
    evenement.preventDefault();
    enregistrer.mutate(
      {
        in_app_enabled: p.in_app_enabled,
        email_enabled: p.email_enabled && p.email_consent_given,
        email_recipient: p.email_recipient?.trim() || null,
        email_consent_given: p.email_consent_given,
        notify_new_offers: p.notify_new_offers,
        notify_relevant_matches: p.notify_relevant_matches,
        min_relevance_score: p.min_relevance_score,
        notify_search_errors: p.notify_search_errors,
        notify_follow_up_reminders: p.notify_follow_up_reminders,
        notify_ai_budget_alerts: p.notify_ai_budget_alerts,
        daily_digest_enabled: p.daily_digest_enabled,
        daily_digest_time: p.daily_digest_time,
      },
      {
        onSuccess: () => toast.success("Préférences de notification enregistrées."),
        onError: (erreur) => toast.error(erreur.message),
      },
    );
  };

  return (
    <form
      aria-label="Préférences de notification"
      onSubmit={soumettre}
      className="flex flex-col gap-4"
    >
      <Case
        libelle="Afficher les notifications dans l'application"
        coche={p.in_app_enabled}
        onChange={(v) => maj("in_app_enabled", v)}
      />
      <fieldset className="flex flex-col gap-2">
        <legend className="pb-1 text-sm font-medium text-foreground">Me prévenir pour</legend>
        {EVENEMENTS.map((e) => (
          <Case key={e.cle} libelle={e.libelle} coche={p[e.cle]} onChange={(v) => maj(e.cle, v)} />
        ))}
        <div className="max-w-xs pt-1">
          <Field label="Compatibilité minimale pour une alerte (0 à 100)">
            {(champ) => (
              <Input
                {...champ}
                type="number"
                min={0}
                max={100}
                value={p.min_relevance_score}
                onChange={(e) =>
                  maj(
                    "min_relevance_score",
                    Math.min(100, Math.max(0, Number(e.target.value) || 0)),
                  )
                }
              />
            )}
          </Field>
        </div>
      </fieldset>
      <div className="flex flex-wrap items-end gap-4">
        <Case
          libelle="Résumé quotidien"
          coche={p.daily_digest_enabled}
          onChange={(v) => maj("daily_digest_enabled", v)}
        />
        <Field label="Heure du résumé">
          {(champ) => (
            <Input
              {...champ}
              type="time"
              value={p.daily_digest_time}
              onChange={(e) => maj("daily_digest_time", e.target.value)}
            />
          )}
        </Field>
      </div>

      <fieldset className="flex flex-col gap-3 rounded-md border border-border p-3">
        <legend className="px-1 text-sm font-medium text-foreground">Envoi par e-mail</legend>
        <p className="text-sm text-foreground-muted">
          Le contenu des notifications (titres d&apos;offres, entreprises, relances) quitterait
          cette machine pour être envoyé à l&apos;adresse indiquée. Rien n&apos;est envoyé sans
          votre accord explicite ci-dessous.
        </p>
        <Case
          libelle="J'accepte l'envoi de ces notifications par e-mail à l'adresse ci-dessous"
          coche={p.email_consent_given}
          onChange={(v) => {
            maj("email_consent_given", v);
            if (!v) maj("email_enabled", false);
          }}
        />
        <Field label="Adresse e-mail">
          {(champ) => (
            <Input
              {...champ}
              type="email"
              value={p.email_recipient ?? ""}
              maxLength={254}
              onChange={(e) => maj("email_recipient", e.target.value)}
            />
          )}
        </Field>
        <Case
          libelle="Activer l'envoi par e-mail"
          coche={p.email_enabled}
          disabled={!p.email_consent_given}
          onChange={(v) => maj("email_enabled", v)}
        />
      </fieldset>
      <div>
        <Button type="submit" loading={enregistrer.isPending} disabled={!emailValide}>
          Enregistrer
        </Button>
      </div>
    </form>
  );
}

/** Préférences de notification (TASK-017-24) : canaux, événements, résumé quotidien, e-mail. */
export function NotificationSettingsPanel() {
  const preferences = useQuery({ queryKey: CLE, queryFn: getNotificationPreferences });
  return (
    <Panel title="Notifications">
      {preferences.isPending ? (
        <Skeleton className="h-40 w-full" role="status" aria-label="Chargement" />
      ) : preferences.isError ? (
        <p role="alert" className="text-sm">
          Impossible de lire vos préférences de notification : {preferences.error.message}
        </p>
      ) : (
        <Formulaire initial={preferences.data} />
      )}
    </Panel>
  );
}
