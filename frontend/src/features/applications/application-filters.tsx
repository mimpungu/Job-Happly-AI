"use client";

import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { statusLabel } from "@/components/ui/status-badge";
import { APPLICATION_STATUSES } from "@/types/application-status";
import type { ApplicationFilters } from "@/types/applications";

import { EMPTY_FILTERS, FOLLOW_UP_OPTIONS } from "./filters";

const STATUS_OPTIONS = APPLICATION_STATUSES.map((s) => ({ value: s, label: statusLabel(s) }));

export function ApplicationFiltersForm({
  filters,
  onSubmit,
}: {
  filters: ApplicationFilters;
  onSubmit: (filters: ApplicationFilters) => void;
}) {
  const [brouillon, setBrouillon] = useState(filters);
  const maj = <K extends keyof ApplicationFilters>(cle: K, valeur: ApplicationFilters[K]) =>
    setBrouillon((b) => ({ ...b, [cle]: valeur }));

  const soumettre = (e: FormEvent) => {
    e.preventDefault();
    onSubmit({ ...brouillon, page: 1 });
  };

  return (
    <form
      onSubmit={soumettre}
      role="search"
      aria-label="Filtrer les candidatures"
      className="grid gap-4 rounded-lg border border-border bg-background-secondary p-4 md:grid-cols-2 lg:grid-cols-4"
    >
      <Field label="Statut">
        {({ id }) => (
          <Select
            id={id}
            options={STATUS_OPTIONS}
            placeholder="Tous les statuts"
            value={brouillon.status}
            onChange={(e) => maj("status", e.target.value as ApplicationFilters["status"])}
          />
        )}
      </Field>
      <Field label="Entreprise">
        {(c) => (
          <Input
            {...c}
            value={brouillon.company}
            maxLength={200}
            onChange={(e) => maj("company", e.target.value)}
          />
        )}
      </Field>
      <Field label="Intitulé du poste">
        {(c) => (
          <Input
            {...c}
            value={brouillon.title}
            maxLength={200}
            onChange={(e) => maj("title", e.target.value)}
          />
        )}
      </Field>
      <Field label="Relance">
        {({ id }) => (
          <Select
            id={id}
            options={FOLLOW_UP_OPTIONS}
            placeholder="Toutes"
            value={brouillon.followUp}
            onChange={(e) => maj("followUp", e.target.value as ApplicationFilters["followUp"])}
          />
        )}
      </Field>
      <div className="flex gap-3 md:col-span-2 lg:col-span-4">
        <Button type="submit">Filtrer</Button>
        <Button
          variant="ghost"
          onClick={() => {
            setBrouillon(EMPTY_FILTERS);
            onSubmit(EMPTY_FILTERS);
          }}
        >
          Réinitialiser
        </Button>
      </div>
    </form>
  );
}
