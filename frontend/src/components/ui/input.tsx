import { Search, X } from "lucide-react";
import { useId, useState, type ChangeEvent, type InputHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

const champBase = [
  "w-full h-10 rounded-md border bg-background-secondary px-3 text-sm text-foreground",
  "placeholder:text-foreground-subtle transition-colors",
  "duration-(--duration-fast) ease-(--ease-standard)",
  "disabled:cursor-not-allowed disabled:opacity-(--disabled-opacity)",
].join(" ");

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  /** Signale une valeur invalide (bordure d'erreur et `aria-invalid`). */
  invalid?: boolean;
}

export function Input({ className, invalid = false, ...props }: InputProps) {
  return (
    <input
      className={cn(
        champBase,
        invalid ? "border-danger" : "border-border hover:border-border-strong",
        className,
      )}
      aria-invalid={invalid || undefined}
      {...props}
    />
  );
}

export interface FieldProps {
  label: string;
  /** Message d'aide affiché sous le champ. */
  hint?: string;
  /** Message d'erreur : remplace l'aide et marque le champ invalide. */
  error?: string;
  children: (champ: {
    id: string;
    invalid: boolean;
    "aria-describedby": string | undefined;
  }) => React.ReactNode;
}

/** Associe un libellé, une aide et une erreur à un champ de formulaire. */
export function Field({ label, hint, error, children }: FieldProps) {
  const id = useId();
  const descriptionId = error || hint ? `${id}-description` : undefined;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium text-foreground">
        {label}
      </label>
      {children({ id, invalid: Boolean(error), "aria-describedby": descriptionId })}
      {error ? (
        <p id={descriptionId} role="alert" className="text-xs text-danger">
          {error}
        </p>
      ) : hint ? (
        <p id={descriptionId} className="text-xs text-foreground-muted">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

export interface SearchInputProps extends Omit<InputProps, "type" | "onChange"> {
  onValueChange?: (valeur: string) => void;
  /** Libellé accessible du bouton d'effacement. */
  clearLabel?: string;
}

export function SearchInput({
  className,
  onValueChange,
  clearLabel = "Effacer la recherche",
  defaultValue = "",
  ...props
}: SearchInputProps) {
  const [valeur, setValeur] = useState(String(defaultValue));
  const changer = (nouvelle: string) => {
    setValeur(nouvelle);
    onValueChange?.(nouvelle);
  };
  return (
    <div className="relative">
      <Search
        className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-foreground-subtle"
        aria-hidden="true"
      />
      <Input
        type="search"
        className={cn("pl-9 pr-9 [&::-webkit-search-cancel-button]:hidden", className)}
        value={valeur}
        onChange={(e: ChangeEvent<HTMLInputElement>) => changer(e.target.value)}
        {...props}
      />
      {valeur ? (
        <button
          type="button"
          aria-label={clearLabel}
          onClick={() => changer("")}
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded-sm p-1 text-foreground-muted hover:text-foreground"
        >
          <X className="size-4" aria-hidden="true" />
        </button>
      ) : null}
    </div>
  );
}
