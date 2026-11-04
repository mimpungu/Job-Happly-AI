import type { Metadata } from "next";

import { CvStudio } from "@/features/documents/cv-studio";

export const metadata: Metadata = { title: "Espace CV — Happly AI" };

export default function Page() {
  return <CvStudio />;
}
