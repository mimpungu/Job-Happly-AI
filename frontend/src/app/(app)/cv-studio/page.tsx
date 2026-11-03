import type { Metadata } from "next";
import { FileText } from "lucide-react";

import { SectionPage } from "@/features/shell/section-page";

export const metadata: Metadata = { title: "Espace CV — Happly AI" };

export default function Page() {
  return (
    <SectionPage
      title="Espace CV"
      icon={FileText}
      emptyTitle="Aucun CV maître"
      emptyDescription="Importez votre CV pour constituer votre profil de référence."
    />
  );
}
