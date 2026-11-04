import type { Metadata } from "next";
import { MessagesSquare } from "lucide-react";

import { SectionPage } from "@/features/shell/section-page";

export const metadata: Metadata = { title: "Préparation d'entretien — Happly AI" };

export default function Page() {
  return (
    <SectionPage
      title="Préparation d'entretien"
      icon={MessagesSquare}
      emptyTitle="Aucune préparation"
      emptyDescription="Préparez un entretien à partir d'une candidature, à la demande."
    />
  );
}
