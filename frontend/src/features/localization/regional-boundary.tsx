"use client";

import { Fragment } from "react";

import { useLocaleSetting } from "@/i18n/locale-provider";
import { setRegional } from "@/lib/regional";

import { usePreferences } from "./use-localization";

/**
 * Applique aux formateurs la langue, le pays et le fuseau des préférences (TASK-017-03, 017-05).
 *
 * Les formateurs lisent des réglages globaux : quand l'un d'eux change, le sous-arbre est remonté
 * (clé) pour que tout l'affichage soit recalculé. Les données restent dans le cache des requêtes,
 * placé au-dessus : rien n'est rechargé.
 */
export function RegionalBoundary({ children }: { children: React.ReactNode }) {
  const { locale } = useLocaleSetting();
  const preferences = usePreferences();
  const country = preferences.data?.country_code ?? null;
  const timeZone = preferences.data?.timezone ?? null;
  // Écriture idempotente d'un réglage global, nécessaire avant le rendu des enfants.
  setRegional({ locale, country, timeZone });
  return <Fragment key={`${locale}|${country}|${timeZone}`}>{children}</Fragment>;
}
