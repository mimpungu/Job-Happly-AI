import type { Metadata } from "next";
import { BriefcaseBusiness } from "lucide-react";

import { SectionPage } from "@/features/shell/section-page";

export const metadata: Metadata = { title: "Candidatures — Happly AI" };

export default function Page() {
  return (
    <SectionPage
      title="Candidatures"
      icon={BriefcaseBusiness}
      emptyTitle="Aucune candidature"
      emptyDescription="Suivez ici l'avancement de vos candidatures, en tableau ou en Kanban."
    />
  );
}
