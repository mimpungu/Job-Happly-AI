"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { ItemSection, ProfileDocument } from "@/types/profile";

import { HistoryPanel } from "./history-panel";
import { PreferencesSection } from "./preferences-section";
import {
  CertificationsSection,
  EducationsSection,
  ExperiencesSection,
  IdentitySection,
  LanguagesSection,
  SkillsSection,
  type SectionProps,
} from "./sections";

export interface ProfileTabsProps {
  doc: ProfileDocument;
  /** Version validée ou ancienne version consultée : aucun champ n'est modifiable. */
  readOnly: boolean;
  onChange: (doc: ProfileDocument) => void;
  section: SectionProps;
}

/** Les sept onglets du profil, communs à l'édition et à la consultation d'une version. */
export function ProfileTabs({ doc, readOnly, onChange, section }: ProfileTabsProps) {
  const total = (cle: ItemSection) => doc[cle].length;
  return (
    <Tabs defaultValue="identite">
      <TabsList className="flex-wrap">
        <TabsTrigger value="identite">Identité</TabsTrigger>
        <TabsTrigger value="experiences">Expériences ({total("experiences")})</TabsTrigger>
        <TabsTrigger value="formations">Formations ({total("educations")})</TabsTrigger>
        <TabsTrigger value="competences">Compétences ({total("skills")})</TabsTrigger>
        <TabsTrigger value="langues">Langues et certifications</TabsTrigger>
        <TabsTrigger value="preferences">Préférences</TabsTrigger>
        <TabsTrigger value="historique">Historique</TabsTrigger>
      </TabsList>
      {/* `fieldset disabled` rend tout le formulaire non modifiable pour une version validée. */}
      <fieldset disabled={readOnly} className="min-w-0">
        <TabsContent value="identite">
          <IdentitySection doc={doc} onChange={onChange} />
        </TabsContent>
        <TabsContent value="experiences">
          <ExperiencesSection {...section} />
        </TabsContent>
        <TabsContent value="formations">
          <EducationsSection {...section} />
        </TabsContent>
        <TabsContent value="competences">
          <SkillsSection {...section} />
        </TabsContent>
        <TabsContent value="langues" className="flex flex-col gap-8">
          <LanguagesSection {...section} />
          <CertificationsSection {...section} />
        </TabsContent>
        <TabsContent value="preferences">
          <PreferencesSection doc={doc} onChange={onChange} />
        </TabsContent>
      </fieldset>
      <TabsContent value="historique">
        <HistoryPanel />
      </TabsContent>
    </Tabs>
  );
}
