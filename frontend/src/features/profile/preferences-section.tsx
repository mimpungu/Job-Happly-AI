"use client";

import { useState } from "react";

import { Field, Input } from "@/components/ui/input";
import type { Preferences, ProfileDocument } from "@/types/profile";

import { EMPLOYMENT_TYPES, REMOTE_TYPES } from "@/features/jobs/filters";

/**
 * Liste saisie en texte séparé par des virgules. La valeur n'est validée qu'à la sortie du
 * champ : analyser à chaque frappe effacerait la virgule que l'on vient de taper.
 */
function ListField({
  label,
  hint,
  value,
  onCommit,
  normalize = (v) => v,
}: {
  label: string;
  hint?: string;
  value: string[];
  onCommit: (valeurs: string[]) => void;
  normalize?: (valeur: string) => string;
}) {
  const [texte, setTexte] = useState(value.join(", "));
  const valider = () => {
    const valeurs = [
      ...new Set(
        texte
          .split(",")
          .map((v) => normalize(v.trim()))
          .filter(Boolean),
      ),
    ];
    onCommit(valeurs);
    setTexte(valeurs.join(", "));
  };
  return (
    <Field label={label} hint={hint ?? "Séparez les valeurs par des virgules."}>
      {(champ) => (
        <Input
          {...champ}
          value={texte}
          onChange={(e) => setTexte(e.target.value)}
          onBlur={valider}
        />
      )}
    </Field>
  );
}

function CheckGroup({
  legend,
  options,
  selected,
  onChange,
}: {
  legend: string;
  options: readonly { value: string; label: string }[];
  selected: string[];
  onChange: (valeurs: string[]) => void;
}) {
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="text-sm font-medium text-foreground">{legend}</legend>
      <div className="flex flex-wrap gap-x-4 gap-y-2">
        {options.map((option) => (
          <label key={option.value} className="flex items-center gap-2 text-sm text-foreground">
            <input
              type="checkbox"
              className="size-4 accent-accent"
              checked={selected.includes(option.value)}
              onChange={(e) =>
                onChange(
                  e.target.checked
                    ? [...selected, option.value]
                    : selected.filter((v) => v !== option.value),
                )
              }
            />
            {option.label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export interface PreferencesSectionProps {
  doc: ProfileDocument;
  onChange: (doc: ProfileDocument) => void;
}

export function PreferencesSection({ doc, onChange }: PreferencesSectionProps) {
  const prefs = doc.preferences;
  const maj = (patch: Partial<Preferences>) =>
    onChange({ ...doc, preferences: { ...prefs, ...patch } });
  const salaireSansDevise = Boolean(prefs.salary_min) && !prefs.salary_currency;

  return (
    <section aria-label="Préférences professionnelles" className="flex flex-col gap-4">
      <h2 className="text-lg font-semibold text-foreground">Préférences professionnelles</h2>
      <p className="text-sm text-foreground-muted">
        Elles guident la recherche d&apos;offres et la mise en correspondance. Elles sont conservées
        avec chaque version du profil.
      </p>
      <div className="grid gap-4 sm:grid-cols-2">
        <ListField
          key={`titres-${prefs.job_titles.join("|")}`}
          label="Métiers recherchés"
          value={prefs.job_titles}
          onCommit={(v) => maj({ job_titles: v })}
        />
        <ListField
          key={`villes-${prefs.cities.join("|")}`}
          label="Villes"
          value={prefs.cities}
          onCommit={(v) => maj({ cities: v })}
        />
        <ListField
          key={`pays-${prefs.country_codes.join("|")}`}
          label="Pays"
          hint="Codes ISO séparés par des virgules, ex. FR, BE."
          value={prefs.country_codes}
          normalize={(v) => v.toUpperCase()}
          onCommit={(v) => maj({ country_codes: v })}
        />
        <ListField
          key={`langues-${prefs.application_languages.join("|")}`}
          label="Langues de candidature"
          hint="Codes séparés par des virgules, ex. fr, en."
          value={prefs.application_languages}
          normalize={(v) => v.toLowerCase()}
          onCommit={(v) => maj({ application_languages: v })}
        />
      </div>
      <CheckGroup
        legend="Télétravail"
        options={REMOTE_TYPES}
        selected={prefs.remote_types}
        onChange={(v) => maj({ remote_types: v })}
      />
      <CheckGroup
        legend="Contrats"
        options={EMPLOYMENT_TYPES}
        selected={prefs.employment_types}
        onChange={(v) => maj({ employment_types: v })}
      />
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Salaire annuel souhaité (minimum)">
          {(champ) => (
            <Input
              {...champ}
              type="number"
              min={0}
              inputMode="numeric"
              value={prefs.salary_min ?? ""}
              onChange={(e) => maj({ salary_min: e.target.value === "" ? null : e.target.value })}
            />
          )}
        </Field>
        <Field
          label="Devise"
          error={salaireSansDevise ? "La devise est obligatoire avec un salaire." : undefined}
        >
          {(champ) => (
            <Input
              {...champ}
              maxLength={3}
              value={prefs.salary_currency ?? ""}
              onChange={(e) =>
                maj({
                  salary_currency: e.target.value === "" ? null : e.target.value.toUpperCase(),
                })
              }
            />
          )}
        </Field>
      </div>
    </section>
  );
}
