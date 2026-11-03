import { Suspense } from "react";

import { JobsExplorer } from "@/features/jobs/jobs-explorer";

export default function JobsPage() {
  // `useSearchParams` exige une frontière Suspense (rendu statique de la coquille).
  return (
    <Suspense>
      <JobsExplorer />
    </Suspense>
  );
}
