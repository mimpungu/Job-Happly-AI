import { ChevronDown } from "lucide-react";
import type { SelectHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, "children"> {
  options: readonly SelectOption[];
  /** Option vide initiale (ex. « Tous »). */
  placeholder?: string;
  invalid?: boolean;
}

/** Sélecteur natif stylé : accessible au clavier et aux lecteurs d'écran sans dépendance. */
export function Select({
  options,
  placeholder,
  invalid = false,
  className,
  ...props
}: SelectProps) {
  return (
    <div className="relative">
      <select
        className={cn(
          "h-10 w-full appearance-none rounded-md border bg-background-secondary pl-3 pr-9 text-sm text-foreground",
          "disabled:cursor-not-allowed disabled:opacity-(--disabled-opacity)",
          invalid ? "border-danger" : "border-border hover:border-border-strong",
          className,
        )}
        aria-invalid={invalid || undefined}
        {...props}
      >
        {placeholder !== undefined ? <option value="">{placeholder}</option> : null}
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <ChevronDown
        className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-foreground-muted"
        aria-hidden="true"
      />
    </div>
  );
}
