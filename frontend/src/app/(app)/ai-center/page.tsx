import type { Metadata } from "next";

import { AICenter } from "@/features/ai/ai-center";

export const metadata: Metadata = { title: "Centre IA — Happly AI" };

export default function Page() {
  return <AICenter />;
}
