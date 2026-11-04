import type { Country, Currency, Preferences, PreferencesView } from "@/types/localization";

import { apiFetch } from "./api-client";

export const getPreferences = () => apiFetch<PreferencesView>("/api/v1/preferences");

export const savePreferences = (corps: Preferences) =>
  apiFetch<PreferencesView>("/api/v1/preferences", { method: "PUT", body: JSON.stringify(corps) });

export const listCountries = (locale: string) =>
  apiFetch<Country[]>(`/api/v1/reference/countries?locale=${encodeURIComponent(locale)}`);

export const listCurrencies = (locale: string) =>
  apiFetch<Currency[]>(`/api/v1/reference/currencies?locale=${encodeURIComponent(locale)}`);

export const listTimezones = () => apiFetch<string[]>("/api/v1/reference/timezones");
