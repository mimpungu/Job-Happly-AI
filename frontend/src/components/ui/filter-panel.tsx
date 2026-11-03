import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

import { Button } from "./button";

export interface FilterPanelProps {
  title?: string;
  onReset?: () => void;
  resetLabel?: string;
  className?: string;
  children: ReactNode;
}

/** Conteneur de filtres : regroupe les champs et offre une réinitialisation. */
export function FilterPanel({
  title = "Filtres",
  onReset,
  resetLabel = "Réinitialiser",
  className,
  children,
}: FilterPanelProps) {
  return (
    <form
      aria-label={title}
      onSubmit={(e) => e.preventDefault()}
      className={cn(
        "flex flex-col gap-4 rounded-lg border border-border bg-surface p-4",
        className,
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-foreground">{title}</h2>
        {onReset ? (
          <Button variant="ghost" size="sm" onClick={onReset}>
            {resetLabel}
          </Button>
        ) : null}
      </div>
      {children}
    </form>
  );
}
