"use client";

import { Select } from "@/components/ui/select";
import { DEFAULT_FILTERS } from "@/features/jobs/filters";
import { useOffers } from "@/features/jobs/use-offers";

/** Choix d'une offre parmi les offres déjà collectées (la première page, les plus récentes). */
export function OfferSelect({
  id,
  value,
  onChange,
  placeholder,
  invalid,
  describedBy,
}: {
  id: string;
  value: string;
  onChange: (offerId: string) => void;
  placeholder: string;
  invalid?: boolean;
  describedBy?: string;
}) {
  const offres = useOffers(DEFAULT_FILTERS);
  return (
    <Select
      id={id}
      value={value}
      invalid={invalid}
      aria-describedby={describedBy}
      placeholder={offres.isPending ? "Chargement des offres…" : placeholder}
      disabled={offres.isPending}
      options={(offres.data?.items ?? []).map((o) => ({
        value: o.id,
        label: `${o.title}${o.company_name ? ` — ${o.company_name}` : ""}`,
      }))}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}
