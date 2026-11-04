import { afterEach, describe, expect, it } from "vitest";

import {
  currentTag,
  formatDateParts,
  formatNumber,
  getTimeZone,
  relativeFormatter,
  resetRegional,
  setRegional,
} from "./regional";

const INSTANT = new Date("2026-11-05T23:30:00Z");

afterEach(() => resetRegional());

describe("réglages régionaux", () => {
  it("garde le comportement français par défaut", () => {
    expect(currentTag()).toBe("fr-FR");
    expect(formatNumber(1234.5, { maximumFractionDigits: 1 })).toBe("1\u202f234,5");
    expect(getTimeZone()).toBeUndefined();
  });

  it("suit la langue choisie", () => {
    setRegional({ locale: "en", country: null, timeZone: null });

    expect(currentTag()).toBe("en-GB");
    expect(formatNumber(1234.5, { maximumFractionDigits: 1 })).toBe("1,234.5");
    expect(formatDateParts(INSTANT, { dateStyle: "medium", timeZone: "UTC" })).toBe("5 Nov 2026");
  });

  it("précise l'usage avec le pays des préférences", () => {
    setRegional({ locale: "en", country: "US", timeZone: null });

    expect(currentTag()).toBe("en-US");
    expect(formatDateParts(INSTANT, { dateStyle: "medium", timeZone: "UTC" })).toBe("Nov 5, 2026");
  });

  it("retombe sur l'usage par défaut si l'étiquette langue-pays est invalide", () => {
    setRegional({ locale: "fr", country: "1", timeZone: null });

    expect(currentTag()).toBe("fr-FR");
  });

  it("applique le fuseau des préférences, sauf fuseau explicite", () => {
    setRegional({ locale: "fr", country: null, timeZone: "Asia/Tokyo" });

    // 23 h 30 UTC, le 5 : déjà le 6 à Tokyo.
    expect(formatDateParts(INSTANT, { dateStyle: "short" })).toBe("06/11/2026");
    expect(formatDateParts(INSTANT, { dateStyle: "short", timeZone: "UTC" })).toBe("05/11/2026");
  });

  it("formate les durées relatives dans la langue choisie", () => {
    setRegional({ locale: "en", country: null, timeZone: null });

    expect(relativeFormatter().format(-1, "day")).toBe("yesterday");
  });
});
