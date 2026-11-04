"use client";

import { BriefcaseBusiness, ServerCrash } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { cn } from "@/lib/cn";

import { Button, buttonVariants } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Pagination } from "@/components/ui/table";
import { APPLICATIONS_PAGE_SIZE } from "@/services/applications";
import type { ApplicationFilters } from "@/types/applications";

import { ApplicationFiltersForm } from "./application-filters";
import { ApplicationsTable } from "./applications-table";
import {
  EMPTY_FILTERS,
  filtersFromParams,
  filtersToParams,
  viewFromParams,
  type ApplicationView,
} from "./filters";
import { KanbanBoard } from "./kanban-board";
import { StatsStrip } from "./stats-strip";
import { useApplications, useApplicationStats, useKanban } from "./use-applications";

const AUCUN_FILTRE = (f: ApplicationFilters) =>
  !f.status && !f.company.trim() && !f.title.trim() && !f.followUp;

export function ApplicationsExplorer() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  const filters = filtersFromParams(new URLSearchParams(params.toString()));
  const view = viewFromParams(new URLSearchParams(params.toString()));

  // L'URL est la source de vérité : vue et filtres sont partageables et le retour fonctionne.
  const appliquer = (suivants: ApplicationFilters, vue: ApplicationView = view) => {
    const requete = filtersToParams(suivants, vue).toString();
    router.push(requete ? `${pathname}?${requete}` : pathname);
  };

  const stats = useApplicationStats();
  // Chaque vue ne charge que ses propres données.
  const liste = useApplications(filters, view === "table");
  const kanban = useKanban(view === "kanban");

  const pageCount = liste.data
    ? Math.max(1, Math.ceil(liste.data.total / APPLICATIONS_PAGE_SIZE))
    : 1;
  const vide = liste.data?.total === 0 && AUCUN_FILTRE(filters);

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold text-foreground">Candidatures</h1>
      <StatsStrip stats={stats.data} />

      <Tabs
        value={view}
        onValueChange={(v) =>
          appliquer(v === "kanban" ? EMPTY_FILTERS : filters, v as ApplicationView)
        }
      >
        <TabsList aria-label="Vue des candidatures">
          <TabsTrigger value="table">Tableau</TabsTrigger>
          <TabsTrigger value="kanban">Kanban</TabsTrigger>
        </TabsList>

        <TabsContent value="table" className="flex flex-col gap-4">
          <ApplicationFiltersForm key={params.toString()} filters={filters} onSubmit={appliquer} />
          <section
            aria-label="Résultats"
            aria-busy={liste.isPlaceholderData || undefined}
            className={cn("flex flex-col gap-4", liste.isPlaceholderData && "opacity-60")}
          >
            {liste.isPending ? (
              <div
                className="flex flex-col gap-2"
                role="status"
                aria-label="Chargement des candidatures"
              >
                {Array.from({ length: 5 }, (_, i) => (
                  <Skeleton key={i} className="h-14 w-full" />
                ))}
              </div>
            ) : liste.isError ? (
              <EmptyState
                icon={ServerCrash}
                title="Impossible de charger les candidatures"
                description={liste.error.message}
                action={<Button onClick={() => void liste.refetch()}>Réessayer</Button>}
              />
            ) : vide ? (
              <AucuneCandidature />
            ) : liste.data.items.length === 0 ? (
              <EmptyState
                icon={BriefcaseBusiness}
                title="Aucune candidature ne correspond"
                description="Aucune candidature ne correspond à ces filtres. Élargissez-les ou réinitialisez-les."
                action={
                  <Button variant="secondary" onClick={() => appliquer(EMPTY_FILTERS)}>
                    Réinitialiser les filtres
                  </Button>
                }
              />
            ) : (
              <>
                <p className="text-sm text-foreground-muted" aria-live="polite">
                  {liste.data.total} candidature{liste.data.total > 1 ? "s" : ""}
                </p>
                <ApplicationsTable applications={liste.data.items} />
                <Pagination
                  page={Math.floor(liste.data.offset / APPLICATIONS_PAGE_SIZE) + 1}
                  pageCount={pageCount}
                  onPageChange={(page) => appliquer({ ...filters, page })}
                />
              </>
            )}
          </section>
        </TabsContent>

        <TabsContent value="kanban">
          {kanban.isPending ? (
            <div role="status" aria-label="Chargement du Kanban">
              <Skeleton className="h-64 w-full" />
            </div>
          ) : kanban.isError ? (
            <EmptyState
              icon={ServerCrash}
              title="Impossible de charger le Kanban"
              description={kanban.error.message}
              action={<Button onClick={() => void kanban.refetch()}>Réessayer</Button>}
            />
          ) : kanban.data.columns.every((c) => c.count === 0) ? (
            <AucuneCandidature />
          ) : (
            <KanbanBoard view={kanban.data} />
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function AucuneCandidature() {
  return (
    <EmptyState
      icon={BriefcaseBusiness}
      title="Aucune candidature"
      description="Suivez ici l'avancement de vos candidatures. Ouvrez une offre et choisissez « Suivre cette candidature » pour commencer."
      action={
        <Link href="/jobs" className={buttonVariants({ variant: "primary" })}>
          Chercher des offres
        </Link>
      }
    />
  );
}
