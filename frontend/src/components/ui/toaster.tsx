"use client";

import { Toaster as Sonner } from "sonner";

export { toast } from "sonner";

/** Conteneur de notifications ; à placer une seule fois dans le layout racine. */
export function Toaster() {
  return (
    <Sonner
      theme="dark"
      position="bottom-right"
      toastOptions={{
        style: {
          background: "var(--color-surface-elevated)",
          color: "var(--color-foreground)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius-md)",
          boxShadow: "var(--shadow-md)",
        },
      }}
    />
  );
}
