import type { Metadata } from "next";
import { Bookmark } from "lucide-react";

import { SectionPage } from "@/features/shell/section-page";

export const metadata: Metadata = { title: "Offres sauvegardées — Happly AI" };

export default function Page() {
  return (
    <SectionPage
      title="Offres sauvegardées"
      icon={Bookmark}
      emptyTitle="Aucune offre sauvegardée"
      emptyDescription="Les offres que vous sauvegarderez depuis les résultats de recherche seront listées ici."
    />
  );
}
