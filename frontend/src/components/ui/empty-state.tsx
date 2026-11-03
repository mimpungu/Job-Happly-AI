import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

export interface EmptyStateProps {
  title: string;
  description: string;
  icon?: LucideIcon;
  /** Action principale proposée à l'utilisateur, si elle existe. */
  action?: ReactNode;
  className?: string;
}

/** État vide explicite : dit ce qui manque et, si possible, comment y remédier. */
export function EmptyState({ title, description, icon: Icon, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border px-6 py-14 text-center",
        className,
      )}
    >
      {Icon ? <Icon className="size-8 text-foreground-subtle" aria-hidden="true" /> : null}
      <h2 className="text-lg font-semibold text-foreground">{title}</h2>
      <p className="max-w-md text-sm text-foreground-muted">{description}</p>
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}
