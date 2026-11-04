import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { OfferDetailView } from "@/features/jobs/offer-detail-view";

// Route dynamique (identifiant inconnu à la compilation) : la navigation de la coquille lit le
// chemin courant, ce qui ne peut pas être prérendu. Le blocage est assumé pour cette seule route.
export const instant = false;

async function Offer({ params }: Pick<PageProps<"/jobs/[id]">, "params">) {
  const { id } = await params;
  return <OfferDetailView id={id} />;
}

export default function OfferPage({ params }: PageProps<"/jobs/[id]">) {
  // La lecture de `params` est dynamique : elle doit rester sous Suspense pour garder la coquille statique.
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <Offer params={params} />
    </Suspense>
  );
}
