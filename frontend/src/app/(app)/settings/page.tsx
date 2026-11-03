import type { Metadata } from "next";
import { Settings } from "lucide-react";

import { SectionPage } from "@/features/shell/section-page";

export const metadata: Metadata = { title: "Paramètres — Happly AI" };

export default function Page() {
  return (
    <SectionPage
      title="Paramètres"
      icon={Settings}
      emptyTitle="Paramètres à venir"
      emptyDescription="Profil, langue, confidentialité et sauvegarde seront configurables ici."
    />
  );
}
