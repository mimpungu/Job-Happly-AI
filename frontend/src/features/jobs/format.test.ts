import { describe, expect, it } from "vitest";

import { formatDate, formatEmployment, formatRemote, formatSalary } from "./format";

const sansSalaire = { salary_min: null, salary_max: null, salary_currency: null };

describe("formatSalary", () => {
  it("n'affiche jamais 0 pour un salaire inconnu", () => {
    expect(formatSalary(sansSalaire)).toBe("Non renseigné");
  });

  it("affiche une fourchette ou une valeur unique avec la devise", () => {
    const fourchette = formatSalary({
      salary_min: "40000.00",
      salary_max: "55000.00",
      salary_currency: "EUR",
    });
    const unique = formatSalary({
      salary_min: "40000.00",
      salary_max: null,
      salary_currency: "EUR",
    });

    expect(fourchette.replace(/\s/g, " ")).toBe("40 000 – 55 000 EUR");
    expect(unique.replace(/\s/g, " ")).toBe("40 000 EUR");
  });
});

describe("libellés", () => {
  it("traduit les valeurs connues, garde les autres, signale l'absence", () => {
    expect(formatEmployment("permanent")).toBe("CDI");
    expect(formatEmployment("inconnu_futur")).toBe("inconnu_futur");
    expect(formatEmployment(null)).toBe("Non renseigné");
    expect(formatRemote("hybrid")).toBe("Hybride");
  });

  it("formate les dates en UTC et refuse les dates invalides", () => {
    expect(formatDate("2026-11-01T23:30:00Z")).toBe("1 nov. 2026");
    expect(formatDate("n'importe quoi")).toBe("Non renseigné");
    expect(formatDate(null)).toBe("Non renseigné");
  });
});
