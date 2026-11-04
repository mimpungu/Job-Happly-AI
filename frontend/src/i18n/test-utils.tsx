import { NextIntlClientProvider } from "next-intl";

import type { Locale } from "./config";
import en from "./messages/en.json";
import fr from "./messages/fr.json";

/** Enveloppe de test : l'interface est rendue dans la langue demandée, sans réseau. */
export function IntlWrapper({
  children,
  locale = "fr",
}: {
  children: React.ReactNode;
  locale?: Locale;
}) {
  return (
    <NextIntlClientProvider locale={locale} messages={locale === "en" ? en : fr} timeZone="UTC">
      {children}
    </NextIntlClientProvider>
  );
}
