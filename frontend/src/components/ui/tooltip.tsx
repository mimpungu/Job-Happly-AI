import { Tooltip as Primitive } from "radix-ui";
import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

export const TooltipProvider = Primitive.Provider;

export interface TooltipProps {
  content: ReactNode;
  children: ReactNode;
  side?: "top" | "right" | "bottom" | "left";
  className?: string;
}

/** Info-bulle complémentaire : jamais le seul moyen d'accéder à une information. */
export function Tooltip({ content, children, side = "top", className }: TooltipProps) {
  return (
    <Primitive.Root>
      <Primitive.Trigger asChild>{children}</Primitive.Trigger>
      <Primitive.Portal>
        <Primitive.Content
          side={side}
          sideOffset={6}
          className={cn(
            "z-50 max-w-xs rounded-md border border-border bg-surface-elevated px-2.5 py-1.5 text-xs text-foreground shadow-md",
            className,
          )}
        >
          {content}
        </Primitive.Content>
      </Primitive.Portal>
    </Primitive.Root>
  );
}
