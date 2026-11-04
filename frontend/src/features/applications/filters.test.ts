import { describe, expect, it } from "vitest";

import { EMPTY_FILTERS, filtersFromParams, filtersToParams, viewFromParams } from "./filters";

describe("filtres d'URL", () => {
  it("lit les filtres reconnus", () => {
    const filtres = filtersFromParams(
      new URLSearchParams("status=sent&company=Acme&title=Dev&relance=due&page=2"),
    );
    expect(filtres).toEqual({
      status: "sent",
      company: "Acme",
      title: "Dev",
      followUp: "due",
      page: 2,
    });
  });

  it("ignore une valeur inconnue plutôt que de la transmettre au serveur", () => {
    const filtres = filtersFromParams(
      new URLSearchParams("status=hacked&relance=toujours&page=-3"),
    );
    expect(filtres).toEqual(EMPTY_FILTERS);
    expect(filtersFromParams(new URLSearchParams("page=abc")).page).toBe(1);
  });

  it("aller-retour : l'URL reproduit exactement les filtres", () => {
    const filtres = {
      status: "interview" as const,
      company: " Acme ",
      title: "",
      followUp: "planned" as const,
      page: 4,
    };
    const relu = filtersFromParams(filtersToParams(filtres, "table"));
    expect(relu).toEqual({ ...filtres, company: "Acme" });
  });

  it("une URL sans filtre reste vide", () => {
    expect(filtersToParams(EMPTY_FILTERS, "table").toString()).toBe("");
  });

  it("mémorise la vue Kanban", () => {
    expect(viewFromParams(new URLSearchParams("vue=kanban"))).toBe("kanban");
    expect(viewFromParams(new URLSearchParams("vue=autre"))).toBe("table");
    expect(filtersToParams(EMPTY_FILTERS, "kanban").toString()).toBe("vue=kanban");
  });
});
