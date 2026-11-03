"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { offersKey } from "@/features/jobs/use-offers";
import {
  addCompany,
  discoverCompany,
  getFranceTravailStatus,
  listCompanies,
  runCollection,
  searchFranceTravail,
  setCompanyEnabled,
} from "@/services/companies";

export const COMPANIES_KEY = ["companies"] as const;

export const useCompanies = () => useQuery({ queryKey: COMPANIES_KEY, queryFn: listCompanies });

export const useDiscoverCompany = () =>
  useMutation({ mutationFn: (nom: string) => discoverCompany(nom) });

export function useAddCompany() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: addCompany,
    onSuccess: () => void client.invalidateQueries({ queryKey: COMPANIES_KEY }),
  });
}

export function useSetCompanyEnabled() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      setCompanyEnabled(id, enabled),
    onSuccess: () => void client.invalidateQueries({ queryKey: COMPANIES_KEY }),
  });
}

/** Une collecte change les offres, l'état des sources et donc les scores affichés. */
export function useRunCollection() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: runCollection,
    onSettled: () => {
      void client.invalidateQueries({ queryKey: COMPANIES_KEY });
      void client.invalidateQueries({ queryKey: offersKey });
    },
  });
}

export const useFranceTravailStatus = () =>
  useQuery({ queryKey: ["france-travail", "status"], queryFn: getFranceTravailStatus });

export function useFranceTravailSearch() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: searchFranceTravail,
    onSettled: () => void client.invalidateQueries({ queryKey: offersKey }),
  });
}
