import type { LucideIcon } from "lucide-react";

import { EmptyState } from "@/components/ui/empty-state";

export interface SectionPageProps {
  title: string;
  icon: LucideIcon;
  /** Ce que l'utilisateur verra ici, et ce qui est nécessaire pour que ce soit disponible. */
  emptyTitle: string;
  emptyDescription: string;
}

/** Page de section sans donnée : n'affiche jamais de faux contenu. */
export function SectionPage({ title, icon, emptyTitle, emptyDescription }: SectionPageProps) {
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold text-foreground">{title}</h1>
      <EmptyState icon={icon} title={emptyTitle} description={emptyDescription} />
    </div>
  );
}
