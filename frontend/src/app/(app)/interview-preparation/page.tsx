import type { Metadata } from "next";
import { Suspense } from "react";

import { InterviewHub } from "@/features/interview-preparation/interview-hub";

export const metadata: Metadata = { title: "Préparation d'entretien — Happly AI" };

export default function Page() {
  // `useSearchParams` exige une frontière Suspense (rendu statique de la coquille).
  return (
    <Suspense>
      <InterviewHub />
    </Suspense>
  );
}
