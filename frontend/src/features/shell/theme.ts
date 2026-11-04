export type Theme = "light" | "dark";

export const THEME_STORAGE_KEY = "happly-theme";

/** Thème effectivement appliqué à la page (l'attribut est posé avant le premier rendu). */
export function currentTheme(): Theme {
  return document.documentElement.dataset.theme === "light" ? "light" : "dark";
}

export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // Stockage indisponible (navigation privée) : le choix vaut pour la session en cours.
  }
}

export function subscribeToTheme(onChange: () => void): () => void {
  const observateur = new MutationObserver(onChange);
  observateur.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-theme"],
  });
  return () => observateur.disconnect();
}
