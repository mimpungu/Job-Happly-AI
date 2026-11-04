"use client";

import { Moon, Sun } from "lucide-react";
import { useSyncExternalStore } from "react";

import { IconButton } from "@/components/ui/icon-button";

import { applyTheme, currentTheme, subscribeToTheme, type Theme } from "./theme";

/** Bascule clair/sombre ; le choix est mémorisé dans le navigateur. */
export function ThemeToggle() {
  // Côté serveur le thème est inconnu : « dark » (défaut), corrigé dès l'hydratation.
  const theme = useSyncExternalStore<Theme>(subscribeToTheme, currentTheme, () => "dark");
  const cible: Theme = theme === "dark" ? "light" : "dark";

  return (
    <IconButton
      variant="circle"
      size="lg"
      aria-label={cible === "light" ? "Passer au thème clair" : "Passer au thème sombre"}
      onClick={() => applyTheme(cible)}
    >
      {theme === "dark" ? (
        <Sun className="size-5" aria-hidden="true" />
      ) : (
        <Moon className="size-5" aria-hidden="true" />
      )}
    </IconButton>
  );
}
