"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { offersKey } from "@/features/jobs/use-offers";
import { listDataSources, searchSources } from "@/services/sources";
import type { OfferFilters } from "@/types/jobs";

export const SOURCES_KEY = ["sources"] as const;

export const useDataSources = () => useQuery({ queryKey: SOURCES_KEY, queryFn: listDataSources });

export function useSearchSources() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (filters: OfferFilters) => searchSources(filters),
    // De nouvelles offres et l'état des sources ont pu changer.
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: offersKey });
      void client.invalidateQueries({ queryKey: SOURCES_KEY });
    },
  });
}
