import { describe, expect, it } from "vitest";

import {
  formatDay,
  formatDateTime,
  formatPercent,
  isOverdue,
  isoToLocalInput,
  localInputToIso,
} from "./format";

describe("formats", () => {
  it("une date absente ou invalide n'est jamais remplacée par une valeur", () => {
    expect(formatDay(null)).toBe("Non renseignée");
    expect(formatDay("pas une date")).toBe("Non renseignée");
    expect(formatDateTime(null)).toBe("Non renseignée");
  });

  it("formate une date en français", () => {
    expect(formatDay("2026-11-04T12:00:00Z")).toMatch(/4 nov\. 2026/);
  });

  it("un pourcentage absent s'affiche comme absent, jamais comme 0 %", () => {
    expect(formatPercent(null)).toBe("—");
    expect(formatPercent(0)).toBe("0 %");
    expect(formatPercent(33.3)).toBe("33,3 %");
  });

  it("une relance est échue quand sa date est atteinte", () => {
    const maintenant = new Date("2026-11-04T12:00:00Z");
    expect(isOverdue("2026-11-04T12:00:00Z", maintenant)).toBe(true);
    expect(isOverdue("2026-11-03T12:00:00Z", maintenant)).toBe(true);
    expect(isOverdue("2026-11-05T12:00:00Z", maintenant)).toBe(false);
    expect(isOverdue(null, maintenant)).toBe(false);
  });

  it("convertit une saisie locale en instant avec fuseau, et inversement", () => {
    const iso = localInputToIso("2026-11-04T09:30");
    expect(iso).toMatch(/Z$/);
    expect(isoToLocalInput(new Date(iso as string))).toBe("2026-11-04T09:30");
    expect(localInputToIso("")).toBeUndefined();
    expect(localInputToIso("n'importe quoi")).toBeUndefined();
  });
});
