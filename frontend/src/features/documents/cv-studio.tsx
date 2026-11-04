"use client";

import { ProfileEditor } from "@/features/profile/profile-editor";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { CvLibrary } from "./cv-library";

/** Espace CV : le profil maître (source de vérité) et les CV générés à partir de lui. */
export function CvStudio() {
  return (
    <Tabs defaultValue="profile">
      <TabsList aria-label="Espace CV">
        <TabsTrigger value="profile">Profil maître</TabsTrigger>
        <TabsTrigger value="documents">CV générés</TabsTrigger>
      </TabsList>
      <TabsContent value="profile">
        <ProfileEditor />
      </TabsContent>
      <TabsContent value="documents">
        <div className="flex flex-col gap-6">
          <h1 className="text-2xl font-semibold text-foreground">Espace CV</h1>
          <CvLibrary />
        </div>
      </TabsContent>
    </Tabs>
  );
}
