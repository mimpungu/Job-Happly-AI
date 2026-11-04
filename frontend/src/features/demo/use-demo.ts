"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { disableDemo, enableDemo, getDemo } from "@/services/demo";

const key = ["demo"] as const;

export const useDemo = () => useQuery({ queryKey: key, queryFn: getDemo, retry: false });

/** Activer ou désactiver change les offres, candidatures et documents : on relit tout. */
function useToggle(fn: typeof enableDemo) {
  const client = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: () => client.invalidateQueries() });
}

export const useEnableDemo = () => useToggle(enableDemo);
export const useDisableDemo = () => useToggle(disableDemo);
