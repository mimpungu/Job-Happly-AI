"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { History, Play, Trash2 } from "lucide-react";
import { useState } from "react";

import { ConfirmDialog } from "@/components/ui/dialog";
import { IconButton } from "@/components/ui/icon-button";
import { Panel } from "@/components/ui/card";
import { toast } from "@/components/ui/toaster";
import {
  deleteSavedSearch,
  listSavedSearches,
  listSearchRuns,
  runSavedSearch,
} from "@/services/jobs";
import type { OfferFilters, SavedSearch } from "@/types/jobs";

import { filtersFromSavedCriteria } from "./filters";
import { formatDate } from "./format";

const SAVED_KEY = ["saved-searches"] as const;
const RUNS_KEY = ["search-runs"] as const;

export function SavedSearchesPanel({ onApply }: { onApply: (filters: OfferFilters) => void }) {
  const client = useQueryClient();
  const [aSupprimer, setASupprimer] = useState<SavedSearch | null>(null);
  const recherches = useQuery({ queryKey: SAVED_KEY, queryFn: listSavedSearches });
  const historique = useQuery({ queryKey: RUNS_KEY, queryFn: listSearchRuns });

  const relancer = useMutation({
    mutationFn: (recherche: SavedSearch) => runSavedSearch(recherche.id),
    onSuccess: (_, recherche) => {
      void client.invalidateQueries({ queryKey: RUNS_KEY });
      onApply(filtersFromSavedCriteria(recherche.offer_filter));
    },
    onError: (erreur) => toast.error(erreur.message),
  });
  const supprimer = useMutation({
    mutationFn: (recherche: SavedSearch) => deleteSavedSearch(recherche.id),
    onSuccess: () => {
      setASupprimer(null);
      void client.invalidateQueries({ queryKey: SAVED_KEY });
      toast.success("Recherche supprimée.");
    },
    onError: (erreur) => toast.error(erreur.message),
  });

  const nomDe = (id: string | null) =>
    recherches.data?.find((r) => r.id === id)?.name ?? "Recherche supprimée";

  return (
    <Panel title="Recherches sauvegardées">
      {recherches.isPending ? (
        <p className="text-sm text-foreground-muted">Chargement…</p>
      ) : recherches.isError ? (
        <p role="alert" className="text-sm text-danger">
          {recherches.error.message}
        </p>
      ) : recherches.data.length === 0 ? (
        <p className="text-sm text-foreground-muted">
          Aucune recherche sauvegardée. Lancez une recherche puis sauvegardez-la pour la relancer en
          un clic.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {recherches.data.map((recherche) => (
            <li key={recherche.id} className="flex items-center justify-between gap-2">
              <span className="truncate text-sm text-foreground">{recherche.name}</span>
              <span className="flex shrink-0 gap-1">
                <IconButton
                  size="sm"
                  aria-label={`Relancer la recherche ${recherche.name}`}
                  disabled={relancer.isPending}
                  onClick={() => relancer.mutate(recherche)}
                >
                  <Play className="size-4" aria-hidden="true" />
                </IconButton>
                <IconButton
                  size="sm"
                  aria-label={`Supprimer la recherche ${recherche.name}`}
                  onClick={() => setASupprimer(recherche)}
                >
                  <Trash2 className="size-4" aria-hidden="true" />
                </IconButton>
              </span>
            </li>
          ))}
        </ul>
      )}

      {historique.data && historique.data.length > 0 ? (
        <div className="mt-4 border-t border-border pt-3">
          <h3 className="mb-2 flex items-center gap-2 text-sm font-medium text-foreground">
            <History className="size-4" aria-hidden="true" />
            Historique
          </h3>
          <ul className="flex flex-col gap-1 text-xs text-foreground-muted">
            {historique.data.map((execution) => (
              <li key={execution.id}>
                {formatDate(execution.started_at)} · {nomDe(execution.saved_search_id)} ·{" "}
                {execution.result_count ?? 0} offre(s)
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <ConfirmDialog
        open={aSupprimer !== null}
        onOpenChange={(ouvert) => !ouvert && setASupprimer(null)}
        title="Supprimer cette recherche ?"
        description={`« ${aSupprimer?.name ?? ""} » sera supprimée. Son historique d'exécution est conservé.`}
        confirmLabel="Supprimer"
        destructive
        loading={supprimer.isPending}
        onConfirm={() => aSupprimer && supprimer.mutate(aSupprimer)}
      />
    </Panel>
  );
}
