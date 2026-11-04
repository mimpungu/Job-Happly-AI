import { describe, expect, it } from "vitest";

import {
  DEFAULT_FILTERS,
  filtersFromParams,
  filtersFromSavedCriteria,
  filtersToApiQuery,
  filtersToParams,
  filtersToSavedCriteria,
  parseTitles,
} from "./filters";

const complets = {
  ...DEFAULT_FILTERS,
  text: "python",
  city: "Lyon",
  country: "FR",
  employmentType: "permanent",
  remoteType: "hybrid",
  salaryMin: "45000",
  salaryCurrency: "EUR",
  publishedSince: "2026-10-01",
  minScore: "60",
  sort: "title_asc" as const,
  page: 3,
};

describe("filtres <-> URL", () => {
  it("fait l'aller-retour sans perte", () => {
    const params = filtersToParams(complets);
    expect(filtersFromParams(new URLSearchParams(params.toString()))).toEqual(complets);
  });

  it("n'écrit rien pour les valeurs par défaut", () => {
    expect(filtersToParams(DEFAULT_FILTERS).toString()).toBe("");
  });

  it("retombe sur les défauts pour des valeurs d'URL hostiles", () => {
    const params = new URLSearchParams("sort=<script>&state=x&page=-4&country=fr");
    const filtres = filtersFromParams(params);

    expect(filtres.sort).toBe("published_desc");
    expect(filtres.state).toBe("visible");
    expect(filtres.page).toBe(1);
    expect(filtres.country).toBe("FR");
  });

  it("ignore une page non numérique", () => {
    expect(filtersFromParams(new URLSearchParams("page=abc")).page).toBe(1);
  });

  it("n'écrit la devise qu'avec un salaire", () => {
    expect(filtersToParams({ ...DEFAULT_FILTERS, salaryCurrency: "USD" }).has("currency")).toBe(
      false,
    );
    expect(filtersToParams({ ...DEFAULT_FILTERS, salaryMin: "10" }).get("currency")).toBe("EUR");
  });
});

describe("requête API", () => {
  it("traduit les filtres vers les paramètres de l'API", () => {
    const q = filtersToApiQuery(complets, 25);

    expect(q.get("text")).toBe("python");
    expect(q.get("country_codes")).toBe("FR");
    expect(q.get("employment_types")).toBe("permanent");
    expect(q.get("remote_types")).toBe("hybrid");
    expect(q.get("salary_min")).toBe("45000");
    expect(q.get("salary_currency")).toBe("EUR");
    expect(q.get("published_since")).toBe("2026-10-01T00:00:00Z");
    expect(q.get("min_score")).toBe("60");
    expect([q.get("page"), q.get("page_size"), q.get("sort")]).toEqual(["3", "25", "title_asc"]);
  });

  it("n'envoie pas les filtres vides", () => {
    const q = filtersToApiQuery(DEFAULT_FILTERS, 25);

    expect([...q.keys()].sort()).toEqual(["page", "page_size", "sort", "state"]);
  });
});

describe("recherche sauvegardée", () => {
  it("restitue les critères à l'identique, page remise à 1", () => {
    const criteres = filtersToSavedCriteria(complets);

    expect(criteres).not.toHaveProperty("page");
    expect(filtersFromSavedCriteria(criteres)).toEqual({ ...complets, page: 1 });
  });

  it("supporte des critères partiels ou inattendus", () => {
    const filtres = filtersFromSavedCriteria({ text: "x", country_codes: [], sort: 12 });

    expect(filtres).toEqual({ ...DEFAULT_FILTERS, text: "x" });
  });
});

describe("score minimal", () => {
  it("n'accepte qu'un entier de 0 à 100 dans l'URL", () => {
    expect(filtersFromParams(new URLSearchParams("min_score=70")).minScore).toBe("70");
    expect(filtersFromParams(new URLSearchParams("min_score=0")).minScore).toBe("0");
    for (const hostile of ["101", "-5", "abc", "7.5", "<script>", ""]) {
      expect(filtersFromParams(new URLSearchParams({ min_score: hostile })).minScore).toBe("");
    }
  });

  it("n'écrit rien sans filtre et le propage à l'API et aux recherches sauvegardées", () => {
    expect(filtersToParams(DEFAULT_FILTERS).has("min_score")).toBe(false);
    expect(filtersToApiQuery(DEFAULT_FILTERS, 25).has("min_score")).toBe(false);
    const filtres = { ...DEFAULT_FILTERS, minScore: "60", sort: "score_desc" as const };

    expect(filtersToApiQuery(filtres, 25).get("min_score")).toBe("60");
    expect(filtersToApiQuery(filtres, 25).get("sort")).toBe("score_desc");
    expect(filtersFromSavedCriteria(filtersToSavedCriteria(filtres))).toEqual({
      ...filtres,
      page: 1,
    });
  });
});

describe("filtres de la recherche multilingue, de l'expérience et des intitulés", () => {
  it("fait l'aller-retour URL, API et recherche sauvegardée", () => {
    const filtres = filtersFromParams(
      new URLSearchParams("language=EN&max_experience=3&multilingual=1&titles=Dev, Analyste"),
    );

    expect(filtres).toMatchObject({
      language: "en",
      maxExperience: "3",
      multilingual: true,
      titles: "Dev, Analyste",
    });
    expect(filtersToParams(filtres).get("max_experience")).toBe("3");
    const api = filtersToApiQuery(filtres, 25);
    expect(api.get("max_experience_years")).toBe("3");
    expect(api.get("multilingual")).toBe("true");
    expect(api.get("language")).toBe("en");
    const criteres = filtersToSavedCriteria(filtres);
    // Les intitulés servent aux sources, ils ne font pas partie du filtre des offres.
    expect(criteres).not.toHaveProperty("titles");
    expect(filtersFromSavedCriteria(criteres)).toMatchObject({
      language: "en",
      maxExperience: "3",
      multilingual: true,
    });
  });

  it("ignore une expérience ou une langue invalide venant de l'URL", () => {
    const filtres = filtersFromParams(new URLSearchParams("max_experience=99&language=english"));

    expect(filtres.maxExperience).toBe("");
    expect(filtres.language).toBe("");
  });

  it("nettoie la liste d'intitulés", () => {
    expect(parseTitles(" Dev ,, Dev, Analyste ")).toEqual(["Dev", "Analyste"]);
  });
});
