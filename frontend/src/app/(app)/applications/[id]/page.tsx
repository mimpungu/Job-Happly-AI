import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { ApplicationDetailView } from "@/features/applications/application-detail-view";

// Route dynamique (identifiant inconnu à la compilation) : la navigation de la coquille lit le
// chemin courant, ce qui ne peut pas être prérendu. Le blocage est assumé pour cette seule route.
export const instant = false;

async function Application({ params }: Pick<PageProps<"/applications/[id]">, "params">) {
  const { id } = await params;
  return <ApplicationDetailView id={id} />;
}

export default function ApplicationPage({ params }: PageProps<"/applications/[id]">) {
  // La lecture de `params` est dynamique : elle reste sous Suspense pour garder la coquille statique.
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <Application params={params} />
    </Suspense>
  );
}
