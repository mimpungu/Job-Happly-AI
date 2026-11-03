import type { TextareaHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  invalid?: boolean;
}

export function Textarea({ className, invalid = false, rows = 3, ...props }: TextareaProps) {
  return (
    <textarea
      rows={rows}
      className={cn(
        "w-full rounded-md border bg-background-secondary px-3 py-2 text-sm text-foreground",
        "placeholder:text-foreground-subtle transition-colors",
        "duration-(--duration-fast) ease-(--ease-standard)",
        "disabled:cursor-not-allowed disabled:opacity-(--disabled-opacity)",
        invalid ? "border-danger" : "border-border hover:border-border-strong",
        className,
      )}
      aria-invalid={invalid || undefined}
      {...props}
    />
  );
}
