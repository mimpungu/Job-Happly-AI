import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";

import { cn } from "@/lib/cn";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium whitespace-nowrap",
  {
    variants: {
      variant: {
        neutral: "border-border bg-surface text-foreground-muted",
        accent: "border-accent/40 bg-accent-soft text-on-accent-soft",
        success: "border-success/40 bg-success-soft text-on-success-soft",
        warning: "border-warning/40 bg-warning-soft text-on-warning-soft",
        danger: "border-danger/40 bg-danger-soft text-on-danger-soft",
      },
    },
    defaultVariants: { variant: "neutral" },
  },
);

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
