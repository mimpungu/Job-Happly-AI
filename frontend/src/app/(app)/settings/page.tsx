import type { Metadata } from "next";

import { WeightsEditor } from "@/features/matching/weights-editor";

export const metadata: Metadata = { title: "Paramètres — Happly AI" };

export default function Page() {
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold text-foreground">Paramètres</h1>
      <WeightsEditor />
      <p className="text-sm text-foreground-muted">
        D&apos;autres réglages (langue, confidentialité, sauvegarde) arriveront ici.
      </p>
    </div>
  );
}
