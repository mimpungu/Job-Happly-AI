import type { Metadata } from "next";
import { Search } from "lucide-react";

import { SectionPage } from "@/features/shell/section-page";

export const metadata: Metadata = { title: "Recherche d'emploi — Happly AI" };

export default function Page() {
  return (
    <SectionPage
      title="Recherche d'emploi"
      icon={Search}
      emptyTitle="Aucune recherche lancée"
      emptyDescription="Le moteur de recherche sera disponible une fois une source d'offres configurée."
    />
  );
}
