/** Langues de l'interface réellement traduites (TASK-017-01) : la même liste que le serveur. */
export const LOCALES = ["fr", "en"] as const;
export type Locale = (typeof LOCALES)[number];

export const DEFAULT_LOCALE: Locale = "fr";
export const LOCALE_STORAGE_KEY = "happly-locale";

export const isLocale = (valeur: unknown): valeur is Locale =>
  typeof valeur === "string" && (LOCALES as readonly string[]).includes(valeur);
