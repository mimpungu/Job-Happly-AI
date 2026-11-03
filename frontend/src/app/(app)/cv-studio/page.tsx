import type { Metadata } from "next";

import { ProfileEditor } from "@/features/profile/profile-editor";

export const metadata: Metadata = { title: "Espace CV — Happly AI" };

export default function Page() {
  return <ProfileEditor />;
}
