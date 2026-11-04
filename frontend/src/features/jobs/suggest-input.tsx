"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useId, useState, type InputHTMLAttributes } from "react";

import { Input } from "@/components/ui/input";
import { suggestValues } from "@/services/jobs";

const DELAI_MS = 250;
const MIN_CARACTERES = 2;

export interface SuggestInputProps extends Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "value" | "onChange" | "list"
> {
  field: "title" | "company" | "city";
  value: string;
  onValueChange: (valeur: string) => void;
  /** Champ sans habillage (barre de recherche) : l'appelant fournit le style. */
  bare?: boolean;
}

/**
 * Champ de saisie qui propose, pendant la frappe, des valeurs réellement présentes dans les
 * offres collectées (liste native `datalist` : clavier et lecteurs d'écran gérés par le
 * navigateur). Aucune suggestion inventée ; une panne du serveur ne gêne pas la saisie.
 */
export function SuggestInput({
  field,
  value,
  onValueChange,
  bare = false,
  className,
  ...props
}: SuggestInputProps) {
  const listeId = useId();
  const [stable, setStable] = useState(value.trim());

  // Anti-rebond : on n'interroge pas le serveur à chaque frappe.
  useEffect(() => {
    const minuteur = setTimeout(() => setStable(value.trim()), DELAI_MS);
    return () => clearTimeout(minuteur);
  }, [value]);

  const actif = stable.length >= MIN_CARACTERES;
  const suggestions = useQuery({
    queryKey: ["offers", "suggestions", field, stable],
    queryFn: () => suggestValues(field, stable),
    enabled: actif,
    staleTime: 60_000,
    retry: false,
  });
  // Une suggestion identique à la saisie n'apporte rien.
  const propositions = (actif && Array.isArray(suggestions.data) ? suggestions.data : []).filter(
    (s) => s.toLowerCase() !== value.trim().toLowerCase(),
  );
  const champ = {
    ...props,
    value,
    list: listeId,
    autoComplete: "off",
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => onValueChange(e.target.value),
  };

  return (
    <>
      {bare ? (
        <input className={className} {...champ} />
      ) : (
        <Input className={className} {...champ} />
      )}
      <datalist id={listeId}>
        {propositions.map((s) => (
          <option key={s} value={s} />
        ))}
      </datalist>
    </>
  );
}
