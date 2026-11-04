"use client";

import { MessagesSquare } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { EmptyState } from "@/components/ui/empty-state";
import { Field } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EMPTY_FILTERS } from "@/features/applications/filters";
import { useApplications } from "@/features/applications/use-applications";

import { InterviewsPanel } from "./interviews-panel";
import { PreparationPanel } from "./preparation-panel";
import { SimulationPanel } from "./simulation-panel";

export function InterviewHub() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const candidatures = useApplications(EMPTY_FILTERS);
  const choisie = params.get("application") ?? "";

  const choisir = (id: string) =>
    router.replace(id ? `${pathname}?application=${encodeURIComponent(id)}` : pathname);

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold text-foreground">Préparation d&apos;entretien</h1>

      {candidatures.isPending ? (
        <Skeleton className="h-10 w-full max-w-md" role="status" aria-label="Chargement" />
      ) : candidatures.isError ? (
        <EmptyState
          title="Impossible de charger les candidatures"
          description={candidatures.error.message}
        />
      ) : candidatures.data.items.length === 0 ? (
        <EmptyState
          icon={MessagesSquare}
          title="Aucune candidature"
          description="Suivez une offre depuis la page Candidatures : la préparation d'entretien s'appuie sur elle."
        />
      ) : (
        <div className="max-w-md">
          <Field label="Candidature">
            {(champ) => (
              <Select
                {...champ}
                value={choisie}
                placeholder="Choisir une candidature"
                options={candidatures.data.items.map((c) => ({
                  value: c.id,
                  label: `${c.offer?.title ?? "Offre"}${c.offer?.company_name ? ` — ${c.offer.company_name}` : ""}`,
                }))}
                onChange={(e) => choisir(e.target.value)}
              />
            )}
          </Field>
        </div>
      )}

      {choisie ? (
        <Tabs defaultValue="preparation" key={choisie}>
          <TabsList>
            <TabsTrigger value="preparation">Préparation</TabsTrigger>
            <TabsTrigger value="simulation">Simulation</TabsTrigger>
            <TabsTrigger value="interviews">Entretiens</TabsTrigger>
          </TabsList>
          <TabsContent value="preparation">
            <PreparationPanel applicationId={choisie} />
          </TabsContent>
          <TabsContent value="simulation">
            <SimulationPanel applicationId={choisie} />
          </TabsContent>
          <TabsContent value="interviews">
            <InterviewsPanel applicationId={choisie} />
          </TabsContent>
        </Tabs>
      ) : null}
    </div>
  );
}
