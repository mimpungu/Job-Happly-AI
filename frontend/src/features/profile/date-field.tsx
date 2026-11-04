"use client";

import { useId } from "react";

import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import type { DocDate } from "@/types/profile";

const MOIS = [
  "janvier",
  "février",
  "mars",
  "avril",
  "mai",
  "juin",
  "juillet",
  "août",
  "septembre",
  "octobre",
  "novembre",
  "décembre",
].map((label, i) => ({ value: String(i + 1), label }));

export interface DateFieldProps {
  label: string;
  value: DocDate | null;
  onChange: (valeur: DocDate | null) => void;
  disabled?: boolean;
}

/**
 * Année obligatoire, mois facultatif : un CV ne donne pas toujours le mois, et on ne le devine
 * jamais. Vider l'année efface la date.
 */
export function DateField({ label, value, onChange, disabled }: DateFieldProps) {
  const id = useId();
  return (
    <fieldset className="flex flex-col gap-1.5" disabled={disabled}>
      <legend className="text-sm font-medium text-foreground">{label}</legend>
      <div className="flex gap-2">
        <Input
          aria-label={`${label} — année`}
          id={`${id}-annee`}
          type="number"
          inputMode="numeric"
          min={1950}
          max={2100}
          placeholder="Année"
          className="w-24"
          value={value?.year ?? ""}
          onChange={(e) => {
            const annee = Number.parseInt(e.target.value, 10);
            onChange(Number.isNaN(annee) ? null : { year: annee, month: value?.month ?? null });
          }}
        />
        <Select
          aria-label={`${label} — mois`}
          options={MOIS}
          placeholder="Mois inconnu"
          disabled={!value}
          value={value?.month ? String(value.month) : ""}
          onChange={(e) =>
            value &&
            onChange({ year: value.year, month: e.target.value ? Number(e.target.value) : null })
          }
        />
      </div>
    </fieldset>
  );
}
