"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getPreferences,
  listCountries,
  listCurrencies,
  listTimezones,
  savePreferences,
} from "@/services/localization";

export const PREFERENCES_KEY = ["preferences"] as const;

export const usePreferences = () =>
  useQuery({ queryKey: PREFERENCES_KEY, queryFn: getPreferences });

export function useSavePreferences() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: savePreferences,
    onSuccess: (vue) => client.setQueryData(PREFERENCES_KEY, vue),
  });
}

// Le référentiel ne change pas pendant une session : jamais relu.
const REFERENTIEL = { staleTime: Infinity, gcTime: Infinity } as const;

export const useCountries = (locale: string) =>
  useQuery({
    queryKey: ["reference", "countries", locale],
    queryFn: () => listCountries(locale),
    ...REFERENTIEL,
  });
export const useCurrencies = (locale: string) =>
  useQuery({
    queryKey: ["reference", "currencies", locale],
    queryFn: () => listCurrencies(locale),
    ...REFERENTIEL,
  });
export const useTimezones = () =>
  useQuery({ queryKey: ["reference", "timezones"], queryFn: listTimezones, ...REFERENTIEL });
