import { describe, expect, it } from "vitest";

import { formatRelative } from "./time";

const maintenant = new Date("2026-11-04T12:00:00Z");

describe("formatRelative", () => {
  it("exprime l'écart en unité lisible", () => {
    expect(formatRelative("2026-11-04T11:59:30Z", maintenant)).toBe("à l'instant");
    expect(formatRelative("2026-11-04T11:30:00Z", maintenant)).toBe("il y a 30 minutes");
    expect(formatRelative("2026-11-04T10:00:00Z", maintenant)).toBe("il y a 2 heures");
    expect(formatRelative("2026-11-03T12:00:00Z", maintenant)).toBe("hier");
    expect(formatRelative("2026-11-01T12:00:00Z", maintenant)).toBe("il y a 3 jours");
    expect(formatRelative("2026-08-04T12:00:00Z", maintenant)).toBe("il y a 3 mois");
  });

  it("gère le futur et une date invalide", () => {
    expect(formatRelative("2026-11-05T12:00:00Z", maintenant)).toBe("demain");
    expect(formatRelative("n'importe quoi", maintenant)).toBe("");
  });
});
