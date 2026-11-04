import { describe, expect, it } from "vitest";

import { SUPPORTED_ATS_LIST, SUPPORTED_ATS_TEXT, atsLabel } from "./ats";

describe("libellés des ATS", () => {
  it("nomme chaque ATS lu par le backend", () => {
    expect(atsLabel("ashby")).toBe("Ashby");
    expect(atsLabel("workable")).toBe("Workable");
  });

  it("affiche tel quel un type inconnu plutôt que de l'inventer", () => {
    expect(atsLabel("smartrecruiters")).toBe("smartrecruiters");
  });

  it("énumère les ATS pris en charge dans les textes d'aide", () => {
    expect(SUPPORTED_ATS_TEXT).toBe("Greenhouse, Lever, Ashby ou Workable");
    expect(SUPPORTED_ATS_LIST).toBe("Greenhouse, Lever, Ashby, Workable");
  });
});
