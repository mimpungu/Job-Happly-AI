import type { Metadata } from "next";
import { Mail } from "lucide-react";

import { SectionPage } from "@/features/shell/section-page";

export const metadata: Metadata = { title: "Lettres de motivation — Happly AI" };

export default function Page() {
  return (
    <SectionPage
      title="Lettres de motivation"
      icon={Mail}
      emptyTitle="Aucune lettre"
      emptyDescription="Les lettres générées pour vos candidatures seront conservées ici."
    />
  );
}
