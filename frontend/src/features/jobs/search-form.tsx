"use client";

import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import type { OfferFilters } from "@/types/jobs";

import { DEFAULT_FILTERS, EMPLOYMENT_TYPES, REMOTE_TYPES } from "./filters";

export interface SearchFormProps {
  filters: OfferFilters;
  onSubmit: (filters: OfferFilters) => void;
  onSaveSearch?: (filters: OfferFilters) => void;
}

/**
 * Formulaire de recherche. Les saisies restent locales jusqu'à « Rechercher » : on n'interroge
 * pas l'API à chaque frappe, et la recherche affichée est toujours celle de l'URL.
 */
export function SearchForm({ filters, onSubmit, onSaveSearch }: SearchFormProps) {
  const [draft, setDraft] = useState(filters);
  const maj = <K extends keyof OfferFilters>(cle: K, valeur: OfferFilters[K]) =>
    setDraft((courant) => ({ ...courant, [cle]: valeur }));

  const soumettre = (evenement: FormEvent) => {
    evenement.preventDefault();
    onSubmit({ ...draft, page: 1 });
  };
  const reinitialiser = () => {
    const vide = { ...DEFAULT_FILTERS, sort: draft.sort, state: draft.state };
    setDraft(vide);
    onSubmit(vide);
  };
  const salaireIncomplet = draft.salaryMin.trim() !== "" && !draft.salaryCurrency.trim();

  return (
    <form
      aria-label="Recherche d'offres"
      onSubmit={soumettre}
      className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-4"
    >
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Intitulé, mot-clé ou entreprise">
          {(champ) => (
            <Input
              {...champ}
              value={draft.text}
              maxLength={200}
              onChange={(e) => maj("text", e.target.value)}
            />
          )}
        </Field>
        <Field label="Ville">
          {(champ) => (
            <Input
              {...champ}
              value={draft.city}
              maxLength={200}
              onChange={(e) => maj("city", e.target.value)}
            />
          )}
        </Field>
        <Field label="Pays" hint="Code ISO, ex. FR">
          {(champ) => (
            <Input
              {...champ}
              value={draft.country}
              maxLength={2}
              onChange={(e) => maj("country", e.target.value.toUpperCase())}
            />
          )}
        </Field>
        <Field label="Contrat">
          {({ id }) => (
            <Select
              id={id}
              options={EMPLOYMENT_TYPES}
              placeholder="Tous"
              value={draft.employmentType}
              onChange={(e) => maj("employmentType", e.target.value)}
            />
          )}
        </Field>
        <Field label="Télétravail">
          {({ id }) => (
            <Select
              id={id}
              options={REMOTE_TYPES}
              placeholder="Tous"
              value={draft.remoteType}
              onChange={(e) => maj("remoteType", e.target.value)}
            />
          )}
        </Field>
        <Field label="Salaire minimum" hint="Les offres sans salaire connu sont exclues.">
          {(champ) => (
            <Input
              {...champ}
              type="number"
              min={0}
              inputMode="numeric"
              value={draft.salaryMin}
              onChange={(e) => maj("salaryMin", e.target.value)}
            />
          )}
        </Field>
        <Field
          label="Devise"
          error={salaireIncomplet ? "La devise est obligatoire avec un salaire." : undefined}
        >
          {(champ) => (
            <Input
              {...champ}
              value={draft.salaryCurrency}
              maxLength={3}
              onChange={(e) => maj("salaryCurrency", e.target.value.toUpperCase())}
            />
          )}
        </Field>
        <Field label="Publiée depuis le">
          {(champ) => (
            <Input
              {...champ}
              type="date"
              value={draft.publishedSince}
              onChange={(e) => maj("publishedSince", e.target.value)}
            />
          )}
        </Field>
      </div>
      <div className="flex flex-wrap justify-end gap-3">
        <Button variant="ghost" onClick={reinitialiser}>
          Réinitialiser
        </Button>
        {onSaveSearch ? (
          <Button variant="secondary" onClick={() => onSaveSearch({ ...draft, page: 1 })}>
            Sauvegarder cette recherche
          </Button>
        ) : null}
        <Button type="submit" disabled={salaireIncomplet}>
          Rechercher
        </Button>
      </div>
    </form>
  );
}
