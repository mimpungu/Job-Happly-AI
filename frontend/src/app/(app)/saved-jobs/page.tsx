import { Suspense } from "react";

import { JobsExplorer } from "@/features/jobs/jobs-explorer";

export default function SavedJobsPage() {
  return (
    <Suspense>
      <JobsExplorer savedOnly />
    </Suspense>
  );
}
