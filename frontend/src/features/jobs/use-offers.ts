"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getOffer, listOffers, setOfferState } from "@/services/jobs";
import type { OfferFilters, OfferState } from "@/types/jobs";

export const offersKey = ["offers"] as const;

export function useOffers(filters: OfferFilters) {
  return useQuery({
    queryKey: [...offersKey, "list", filters],
    queryFn: () => listOffers(filters),
    // Garde la page précédente affichée pendant le chargement de la suivante.
    placeholderData: (precedent) => precedent,
  });
}

export function useOffer(id: string) {
  return useQuery({ queryKey: [...offersKey, "detail", id], queryFn: () => getOffer(id) });
}

export function useChangeOfferState() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, state }: { id: string; state: OfferState | null }) =>
      setOfferState(id, state),
    // Le serveur est la source de vérité : on relit les listes et fiches après écriture.
    onSuccess: () => client.invalidateQueries({ queryKey: offersKey }),
  });
}
