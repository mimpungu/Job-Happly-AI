import { DEFAULT_LOCALE, type Locale } from "@/i18n/config";

/**
 * Réglages régionaux courants (TASK-017-03, 017-05) : langue, pays et fuseau horaire choisis par
 * l'utilisateur. Les formateurs de l'application les lisent à chaque appel : aucune date ni aucun
 * nombre ne code « fr-FR » en dur. Sans réglage, le comportement reste français, fuseau du
 * navigateur.
 */
export interface Regional {
  locale: Locale;
  /** Pays ISO 3166-1 alpha-2 des préférences : précise les usages (fr-CA, en-US…). */
  country: string | null;
  /** Fuseau IANA des préférences ; `null` = celui du navigateur. */
  timeZone: string | null;
}

const DEFAUT: Regional = { locale: DEFAULT_LOCALE, country: null, timeZone: null };
let courant: Regional = DEFAUT;

export function setRegional(suivant: Regional): void {
  courant = suivant;
}

export function resetRegional(): void {
  courant = DEFAUT;
}

export const getTimeZone = (): string | undefined => courant.timeZone ?? undefined;

const PAR_DEFAUT: Record<Locale, string> = { fr: "fr-FR", en: "en-GB" };

/** Étiquette BCP 47 : `langue-PAYS` si le navigateur la connaît, sinon l'usage par défaut. */
export function currentTag(): string {
  if (courant.country) {
    const candidate = `${courant.locale}-${courant.country}`;
    try {
      if (Intl.DateTimeFormat.supportedLocalesOf([candidate]).length > 0) return candidate;
    } catch {
      // Étiquette invalide : repli sur l'usage par défaut.
    }
  }
  return PAR_DEFAUT[courant.locale];
}

export function formatNumber(valeur: number, options?: Intl.NumberFormatOptions): string {
  return new Intl.NumberFormat(currentTag(), options).format(valeur);
}

/** Date et/ou heure ; le fuseau explicite d'un appel l'emporte sur celui des préférences. */
export function formatDateParts(valeur: Date, options: Intl.DateTimeFormatOptions): string {
  return new Intl.DateTimeFormat(currentTag(), {
    ...options,
    timeZone: options.timeZone ?? getTimeZone(),
  }).format(valeur);
}

export function relativeFormatter(): Intl.RelativeTimeFormat {
  return new Intl.RelativeTimeFormat(currentTag(), { numeric: "auto" });
}
