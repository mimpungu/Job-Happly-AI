"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "@/components/ui/toaster";
import { isLocale } from "@/i18n/config";
import { useLocaleSetting } from "@/i18n/locale-provider";
import type { PreferencesView } from "@/types/localization";

import {
  useCountries,
  useCurrencies,
  usePreferences,
  useSavePreferences,
  useTimezones,
} from "./use-localization";

const OUI_NON = (oui: string, non: string) => [
  { value: "yes", label: oui },
  { value: "no", label: non },
];

const versTriEtat = (valeur: boolean | null) => (valeur === null ? "" : valeur ? "yes" : "no");
const depuisTriEtat = (valeur: string) => (valeur === "" ? null : valeur === "yes");
const listeDeCodes = (saisie: string) => [
  ...new Set(
    saisie
      .split(",")
      .map((c) => c.trim().toUpperCase())
      .filter(Boolean),
  ),
];

function Formulaire({ initial }: { initial: PreferencesView }) {
  const t = useTranslations("general");
  const { locale, setLocale } = useLocaleSetting();
  const enregistrer = useSavePreferences();
  const pays = useCountries(locale);
  const devises = useCurrencies(locale);
  const fuseaux = useTimezones();

  const [langue, setLangue] = useState(initial.ui_language);
  const [paysPrincipal, setPaysPrincipal] = useState(initial.country_code ?? "");
  const [devise, setDevise] = useState(initial.currency ?? "");
  const [fuseau, setFuseau] = useState(initial.timezone ?? "");
  const [demenager, setDemenager] = useState(versTriEtat(initial.willing_to_relocate));
  const [paysCibles, setPaysCibles] = useState(initial.target_countries.join(", "));
  const [paysPermis, setPaysPermis] = useState(initial.work_permit_countries.join(", "));
  const [parrainage, setParrainage] = useState(versTriEtat(initial.needs_sponsorship));

  const soumettre = (evenement: FormEvent) => {
    evenement.preventDefault();
    enregistrer.mutate(
      {
        ui_language: langue,
        country_code: paysPrincipal || null,
        currency: devise || null,
        timezone: fuseau || null,
        willing_to_relocate: depuisTriEtat(demenager),
        target_countries: listeDeCodes(paysCibles),
        work_permit_countries: listeDeCodes(paysPermis),
        needs_sponsorship: depuisTriEtat(parrainage),
      },
      {
        onSuccess: (vue) => {
          if (isLocale(vue.ui_language)) setLocale(vue.ui_language);
          toast.success(t("saved"));
        },
        onError: (erreur) => toast.error(erreur.message),
      },
    );
  };

  const langues = initial.supported_ui_languages.map((code) => ({
    value: code,
    label: isLocale(code) ? t(`languageNames.${code}`) : code,
  }));

  return (
    <form aria-label={t("title")} onSubmit={soumettre} className="flex flex-col gap-4">
      <p className="text-sm text-foreground-muted">{t("intro")}</p>
      <p className="text-sm">
        <Link href="/cv-studio" className="underline">
          {t("profileLink")}
        </Link>
      </p>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("language")}>
          {({ id }) => (
            <Select
              id={id}
              options={langues}
              value={langue}
              onChange={(e) => setLangue(e.target.value)}
            />
          )}
        </Field>
        <Field label={t("country")}>
          {({ id }) => (
            <Select
              id={id}
              placeholder={t("notSet")}
              options={(pays.data ?? []).map((c) => ({ value: c.code, label: c.name }))}
              value={paysPrincipal}
              onChange={(e) => setPaysPrincipal(e.target.value)}
            />
          )}
        </Field>
        <Field label={t("currency")}>
          {({ id }) => (
            <Select
              id={id}
              placeholder={t("notSet")}
              options={(devises.data ?? []).map((d) => ({
                value: d.code,
                label: `${d.code} — ${d.name}`,
              }))}
              value={devise}
              onChange={(e) => setDevise(e.target.value)}
            />
          )}
        </Field>
        <Field label={t("timezone")}>
          {({ id }) => (
            <Select
              id={id}
              placeholder={t("notSet")}
              options={(fuseaux.data ?? []).map((z) => ({ value: z, label: z }))}
              value={fuseau}
              onChange={(e) => setFuseau(e.target.value)}
            />
          )}
        </Field>
      </div>

      <h3 className="pt-2 text-base font-medium text-foreground">{t("mobilityTitle")}</h3>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("relocate")}>
          {({ id }) => (
            <Select
              id={id}
              placeholder={t("notSet")}
              options={OUI_NON(t("relocateYes"), t("relocateNo"))}
              value={demenager}
              onChange={(e) => setDemenager(e.target.value)}
            />
          )}
        </Field>
        <Field label={t("needsSponsorship")}>
          {({ id }) => (
            <Select
              id={id}
              placeholder={t("notSet")}
              options={OUI_NON(t("sponsorshipYes"), t("sponsorshipNo"))}
              value={parrainage}
              onChange={(e) => setParrainage(e.target.value)}
            />
          )}
        </Field>
        <Field label={t("targetCountries")} hint={t("targetCountriesHint")}>
          {(champ) => (
            <Input
              {...champ}
              value={paysCibles}
              maxLength={200}
              onChange={(e) => setPaysCibles(e.target.value)}
            />
          )}
        </Field>
        <Field label={t("workPermit")} hint={t("targetCountriesHint")}>
          {(champ) => (
            <Input
              {...champ}
              value={paysPermis}
              maxLength={200}
              onChange={(e) => setPaysPermis(e.target.value)}
            />
          )}
        </Field>
      </div>
      <div>
        <Button type="submit" loading={enregistrer.isPending}>
          {t("save")}
        </Button>
      </div>
    </form>
  );
}

/** Paramètres généraux (TASK-017-24) : langue, pays, devise, fuseau horaire et mobilité. */
export function GeneralSettingsPanel() {
  const t = useTranslations("general");
  const preferences = usePreferences();
  return (
    <Panel title={t("title")}>
      {preferences.isPending ? (
        <Skeleton className="h-40 w-full" role="status" aria-label={t("loading")} />
      ) : preferences.isError ? (
        <p role="alert" className="text-sm">
          {t("loadError", { message: preferences.error.message })}
        </p>
      ) : (
        <Formulaire initial={preferences.data} />
      )}
    </Panel>
  );
}
