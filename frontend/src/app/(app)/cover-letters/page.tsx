import type { Metadata } from "next";

import { LettersPage } from "@/features/documents/letters-page";

export const metadata: Metadata = { title: "Lettres de motivation — Happly AI" };

export default function Page() {
  return <LettersPage />;
}
