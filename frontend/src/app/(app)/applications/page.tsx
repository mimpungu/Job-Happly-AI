import type { Metadata } from "next";
import { Suspense } from "react";

import { ApplicationsExplorer } from "@/features/applications/applications-explorer";

export const metadata: Metadata = { title: "Candidatures — Happly AI" };

export default function Page() {
  // `useSearchParams` exige une frontière Suspense (rendu statique de la coquille).
  return (
    <Suspense>
      <ApplicationsExplorer />
    </Suspense>
  );
}
