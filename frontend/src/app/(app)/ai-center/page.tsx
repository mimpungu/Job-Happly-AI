import type { Metadata } from "next";
import { Bot } from "lucide-react";

import { SectionPage } from "@/features/shell/section-page";

export const metadata: Metadata = { title: "Centre IA — Happly AI" };

export default function Page() {
  return (
    <SectionPage
      title="Centre IA"
      icon={Bot}
      emptyTitle="Aucun usage enregistré"
      emptyDescription="Le suivi de la consommation IA et des budgets sera affiché ici."
    />
  );
}
