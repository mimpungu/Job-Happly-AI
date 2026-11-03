import type { HTMLAttributes } from "react";

import { cn } from "@/lib/cn";

/** Zone de chargement à fond uni, sans dégradé ni effet lumineux. */
export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden="true"
      className={cn("animate-pulse rounded-md bg-surface-elevated", className)}
      {...props}
    />
  );
}
