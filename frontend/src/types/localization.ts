/** Contrats de l'API des préférences et du référentiel géographique (docs/API.md). */

export interface Preferences {
  ui_language: string;
  country_code: string | null;
  currency: string | null;
  timezone: string | null;
  willing_to_relocate: boolean | null;
  target_countries: string[];
  work_permit_countries: string[];
  needs_sponsorship: boolean | null;
}

export interface PreferencesView extends Preferences {
  supported_ui_languages: string[];
}

export interface Country {
  code: string;
  name: string;
  official_languages: string[];
  currencies: string[];
}

export interface Currency {
  code: string;
  name: string;
  symbol: string;
}
