import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

const iconButtonVariants = cva(
  [
    "inline-flex shrink-0 items-center justify-center rounded-md border border-transparent",
    "transition-colors duration-(--duration-fast) ease-(--ease-standard)",
    "disabled:pointer-events-none disabled:opacity-(--disabled-opacity)",
  ],
  {
    variants: {
      variant: {
        ghost: "text-foreground-muted hover:bg-surface hover:text-foreground",
        secondary: "border-border bg-surface-elevated text-foreground hover:border-border-strong",
      },
      size: { sm: "size-8", md: "size-10" },
    },
    defaultVariants: { variant: "ghost", size: "md" },
  },
);

export interface IconButtonProps
  extends
    Omit<ButtonHTMLAttributes<HTMLButtonElement>, "aria-label">,
    VariantProps<typeof iconButtonVariants> {
  /** Obligatoire : un bouton-icône n'a pas de texte visible. */
  "aria-label": string;
}

export function IconButton({
  className,
  variant,
  size,
  type = "button",
  ...props
}: IconButtonProps) {
  return (
    <button
      type={type}
      className={cn(iconButtonVariants({ variant, size }), className)}
      {...props}
    />
  );
}
