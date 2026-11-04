"use client";

import { NextIntlClientProvider } from "next-intl";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { DEFAULT_LOCALE, isLocale, LOCALE_STORAGE_KEY, type Locale } from "./config";
import en from "./messages/en.json";
import fr from "./messages/fr.json";

const MESSAGES = { fr, en } as const;

interface LocaleContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
}

const LocaleContext = createContext<LocaleContextValue>({
  locale: DEFAULT_LOCALE,
  setLocale: () => undefined,
});

export const useLocaleSetting = () => useContext(LocaleContext);

/**
 * Langue de l'interface. Le serveur rend toujours le français (aucune lecture de cookie, ce qui
 * garde les pages statiques) ; le choix enregistré est appliqué dès le montage côté navigateur.
 */
export function LocaleProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(DEFAULT_LOCALE);

  useEffect(() => {
    try {
      const enregistre = localStorage.getItem(LOCALE_STORAGE_KEY);
      // Lecture unique du choix enregistré après le montage : la page serveur reste neutre.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      if (isLocale(enregistre)) setLocaleState(enregistre);
    } catch {
      // Stockage indisponible (navigation privée) : on garde la langue par défaut.
    }
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const setLocale = useCallback((suivante: Locale) => {
    setLocaleState(suivante);
    try {
      localStorage.setItem(LOCALE_STORAGE_KEY, suivante);
    } catch {
      // Le choix reste valable pour la session en cours.
    }
  }, []);

  const valeur = useMemo(() => ({ locale, setLocale }), [locale, setLocale]);
  return (
    <LocaleContext.Provider value={valeur}>
      <NextIntlClientProvider locale={locale} messages={MESSAGES[locale]} timeZone="UTC">
        {children}
      </NextIntlClientProvider>
    </LocaleContext.Provider>
  );
}
