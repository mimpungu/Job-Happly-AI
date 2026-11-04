import type { Metadata } from "next";

import { GeneralSettingsPanel } from "@/features/localization/general-settings-panel";
import { DemoPanel } from "@/features/demo/demo-panel";
import { CompaniesPanel } from "@/features/companies/companies-panel";
import { DataSourcesPanel } from "@/features/sources/data-sources-panel";
import { FranceTravailPanel } from "@/features/companies/france-travail-panel";
import { WeightsEditor } from "@/features/matching/weights-editor";
import { HealthPanel } from "@/features/privacy/health-panel";
import { PrivacyPanel } from "@/features/privacy/privacy-panel";

export const metadata: Metadata = { title: "Paramètres — Happly AI" };

export default function Page() {
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold text-foreground">Paramètres</h1>
      <GeneralSettingsPanel />
      <FranceTravailPanel />
      <CompaniesPanel />
      <DataSourcesPanel />
      <WeightsEditor />
      <DemoPanel />
      <PrivacyPanel />
      <HealthPanel />
    </div>
  );
}
