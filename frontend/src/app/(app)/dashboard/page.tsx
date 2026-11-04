import type { Metadata } from "next";
import { LayoutDashboard } from "lucide-react";

import { SectionPage } from "@/features/shell/section-page";

export const metadata: Metadata = { title: "Tableau de bord — Happly AI" };

export default function Page() {
  return (
    <SectionPage
      title="Tableau de bord"
      icon={LayoutDashboard}
      emptyTitle="Aucune donnée pour le moment"
      emptyDescription="Les statistiques apparaîtront ici dès que des recherches et des candidatures existeront."
    />
  );
}
