"use client";

import { SearchX, ServerCrash, UserRoundCheck } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { cn } from "@/lib/cn";

import { Button, buttonVariants } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Field } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Pagination } from "@/components/ui/table";
import { toast } from "@/components/ui/toaster";
import { useRecompute } from "@/features/matching/use-matching";
import { usePreferences } from "@/features/localization/use-localization";
import { QueriedSources } from "@/features/sources/queried-sources";
import { useSearchSources } from "@/features/sources/use-sources";
import { ApiError } from "@/services/api-client";
import type { OfferFilters, OfferSort, OfferState } from "@/types/jobs";

import { filtersFromParams, filtersToParams, SORTS } from "./filters";
import { ManualOfferDialog } from "./manual-offer-dialog";
import { OffersTable } from "./offers-table";
import { SaveSearchDialog } from "./save-search-dialog";
import { SavedSearchesPanel } from "./saved-searches-panel";
import { SearchForm } from "./search-form";
import { useChangeOfferState, useOffers } from "./use-offers";

export interface JobsExplorerProps {
  /** Page « Offres sauvegardées » : l'état est imposé et le formulaire complet n'est pas proposé. */
  savedOnly?: boolean;
}

export function JobsExplorer({ savedOnly = false }: JobsExplorerProps) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [aSauvegarder, setASauvegarder] = useState<OfferFilters | null>(null);

  const preferences = usePreferences();
  const devisePreferee = preferences.data?.currency ?? null;
  const brutUrl = filtersFromParams(new URLSearchParams(params.toString()));
  // Devise par défaut du filtre de salaire : celle des préférences, sauf choix explicite dans
  // l'URL. Aucune conversion n'est faite : c'est seulement la valeur pré-remplie.
  const brut =
    devisePreferee && !params.has("currency")
      ? { ...brutUrl, salaryCurrency: devisePreferee }
      : brutUrl;
  const filters: OfferFilters = savedOnly ? { ...brut, state: "saved" } : brut;

  // L'URL est la source de vérité : recherche reproductible, partageable, bouton retour fonctionnel.
  const appliquer = (suivants: OfferFilters) => {
    const requete = filtersToParams(suivants).toString();
    router.push(requete ? `${pathname}?${requete}` : pathname);
  };

  const offres = useOffers(filters);
  const changerEtat = useChangeOfferState();
  const recalculer = useRecompute();
  const interroger = useSearchSources();
  const modifierEtat = (id: string, state: OfferState | null) =>
    changerEtat.mutate(
      { id, state },
      {
        onSuccess: () =>
          toast.success(
            state === "saved"
              ? "Offre sauvegardée."
              : state === "ignored"
                ? "Offre ignorée."
                : "Offre remise dans la liste.",
          ),
        onError: (erreur) => toast.error(erreur.message),
      },
    );

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold text-foreground">
        {savedOnly ? "Offres sauvegardées" : "Recherche d'emploi"}
      </h1>

      {savedOnly ? null : (
        <SearchForm
          key={`${params.toString()}|${devisePreferee ?? ""}`}
          filters={filters}
          onSubmit={appliquer}
          onSaveSearch={setASauvegarder}
        />
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
        <div className="flex min-w-0 flex-col gap-4">
          <section
            aria-label="Résultats"
            // Pendant le rechargement, l'ancienne page reste affichée : on le signale pour ne pas
            // la faire passer pour à jour.
            aria-busy={offres.isPlaceholderData || undefined}
            className={cn("flex flex-col gap-4", offres.isPlaceholderData && "opacity-60")}
          >
            <div className="flex flex-wrap items-end justify-between gap-3">
              <p className="text-sm text-foreground-muted" aria-live="polite">
                {offres.data
                  ? `${offres.data.total} offre${offres.data.total > 1 ? "s" : ""}`
                  : " "}
              </p>
              <div className="flex flex-wrap items-end gap-3">
                <ManualOfferDialog />
                {savedOnly ? null : (
                  <Button
                    variant="secondary"
                    loading={interroger.isPending}
                    onClick={() =>
                      interroger.mutate(filters, {
                        onSuccess: (r) =>
                          toast.success(
                            r.queried
                              ? `${r.sources.length} source${r.sources.length > 1 ? "s" : ""} interrogée${r.sources.length > 1 ? "s" : ""}.`
                              : "Aucune source activée.",
                          ),
                        onError: (erreur) => toast.error(erreur.message),
                      })
                    }
                  >
                    Interroger les sources
                  </Button>
                )}
                <Button
                  variant="secondary"
                  loading={recalculer.isPending}
                  onClick={() =>
                    recalculer.mutate(undefined, {
                      onSuccess: (r) =>
                        toast.success(
                          `${r.computed} offre${r.computed > 1 ? "s" : ""} évaluée${r.computed > 1 ? "s" : ""}.`,
                        ),
                      onError: (erreur) => toast.error(erreur.message),
                    })
                  }
                >
                  Calculer les scores
                </Button>
                <div className="w-56">
                  <Field label="Trier par">
                    {({ id }) => (
                      <Select
                        id={id}
                        options={SORTS}
                        value={filters.sort}
                        onChange={(e) =>
                          appliquer({ ...filters, sort: e.target.value as OfferSort, page: 1 })
                        }
                      />
                    )}
                  </Field>
                </div>
              </div>
            </div>

            {interroger.data ? <QueriedSources result={interroger.data} /> : null}

            {offres.isPending ? (
              <div className="flex flex-col gap-2" role="status" aria-label="Chargement des offres">
                {Array.from({ length: 5 }, (_, i) => (
                  <Skeleton key={i} className="h-14 w-full" />
                ))}
              </div>
            ) : offres.isError ? (
              offres.error instanceof ApiError && offres.error.code === "scoring_unavailable" ? (
                <EmptyState
                  icon={UserRoundCheck}
                  title="Compatibilité indisponible"
                  description={offres.error.message}
                  action={
                    <Link href="/cv-studio" className={buttonVariants({ variant: "primary" })}>
                      Valider mon profil
                    </Link>
                  }
                />
              ) : (
                <EmptyState
                  icon={ServerCrash}
                  title="Impossible de charger les offres"
                  description={offres.error.message}
                  action={<Button onClick={() => void offres.refetch()}>Réessayer</Button>}
                />
              )
            ) : offres.data.items.length === 0 ? (
              <EmptyState
                icon={SearchX}
                title={savedOnly ? "Aucune offre sauvegardée" : "Aucune offre ne correspond"}
                description={
                  savedOnly
                    ? "Sauvegardez une offre depuis la recherche pour la retrouver ici."
                    : "Aucune offre collectée ne correspond à ces critères. Élargissez la recherche ; les offres apparaissent une fois les entreprises suivies et collectées."
                }
                action={
                  savedOnly ? undefined : (
                    <Link href="/settings" className={buttonVariants({ variant: "secondary" })}>
                      Suivre des entreprises
                    </Link>
                  )
                }
              />
            ) : (
              <>
                <OffersTable
                  offers={offres.data.items}
                  onChangeState={modifierEtat}
                  busy={changerEtat.isPending}
                />
                <Pagination
                  page={offres.data.page}
                  pageCount={offres.data.page_count}
                  onPageChange={(page) => appliquer({ ...filters, page })}
                />
              </>
            )}
          </section>
        </div>

        <aside aria-label="Recherches sauvegardées">
          <SavedSearchesPanel onApply={appliquer} />
        </aside>
      </div>

      <SaveSearchDialog filters={aSauvegarder} onClose={() => setASauvegarder(null)} />
    </div>
  );
}
