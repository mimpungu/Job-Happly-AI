import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const TAILLES = [
  { nom: "mobile", width: 390, height: 800 },
  { nom: "tablette", width: 768, height: 1024 },
  { nom: "bureau", width: 1280, height: 800 },
];
const THEMES = ["dark", "light"] as const;

const offres = {
  items: [{ id: "o1", title: "Développeur Python", company_name: "Acme" }],
  total: 1,
  page: 1,
  page_size: 25,
  page_count: 1,
};
const cv = [
  {
    id: "d1",
    title: "CV - Développeur Python",
    language: "fr",
    offer_id: "o1",
    created_at: "2026-11-04T10:00:00Z",
    versions: [
      {
        id: "v1",
        version: 1,
        created_at: "2026-11-04T10:00:00Z",
        size_bytes: 52_000,
        ats_report: {
          score: 94,
          passed: true,
          checks: [],
          page_count: 1,
          keywords_found: ["Python"],
          keywords_missing: ["Kubernetes"],
        },
        generation: {
          origin: "generated",
          ai_rewrite: {
            requested: "ai",
            status: "unavailable",
            rewritten: 0,
            rejected: 0,
            provider: null,
            reason: "Plafond atteint.",
          },
        },
      },
    ],
  },
];
const lettres = [
  {
    id: "l1",
    title: "Lettre - Développeur Python (Acme)",
    language: "fr",
    offer_id: "o1",
    created_at: "2026-11-04T10:00:00Z",
    content: null,
    versions: [
      {
        id: "lv1",
        version: 1,
        created_at: "2026-11-04T10:00:00Z",
        size_bytes: 40_000,
        audit: {
          score: 82,
          passed: true,
          word_count: 280,
          length_status: "optimal",
          cv_coherent: true,
          page_count: 1,
          spelling_issues: [],
          generic_phrases_detected: [],
          issues: ["Aucune demande d'entretien."],
        },
      },
    ],
  },
];

async function simulerApi(page: Page) {
  await page.route("**/api/v1/**", async (route) => {
    const { pathname } = new URL(route.request().url());
    if (pathname.endsWith("/offers")) return route.fulfill({ json: offres });
    if (pathname.endsWith("/resumes")) return route.fulfill({ json: cv });
    if (pathname.endsWith("/cover-letters")) return route.fulfill({ json: lettres });
    return route.fulfill({
      status: 404,
      json: { error: { code: "profile_not_found", message: "Aucun profil." } },
    });
  });
}

for (const theme of THEMES)
  for (const { nom, width, height } of TAILLES) {
    test.describe(`thème ${theme}, écran ${nom}`, () => {
      test.use({ viewport: { width, height } });

      for (const ecran of ["lettres", "cv"] as const) {
        test(`${ecran === "cv" ? "Espace CV (CV générés)" : "Lettres de motivation"} : aucune violation d'accessibilité ni débordement`, async ({
          page,
        }) => {
          await page.addInitScript((t) => localStorage.setItem("happly-theme", t), theme);
          await simulerApi(page);
          if (ecran === "lettres") {
            await page.goto("/cover-letters");
            await expect(page.getByText("Qualité 82/100")).toBeVisible();
          } else {
            await page.goto("/cv-studio");
            await page.getByRole("tab", { name: "CV générés" }).click();
            await expect(page.getByText("ATS 94/100")).toBeVisible();
          }
          await expect(page.getByRole("status", { name: "Chargement" })).toHaveCount(0);

          const resultat = await new AxeBuilder({ page })
            .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
            .analyze();
          const debordement = await page.evaluate(
            () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
          );

          expect(resultat.violations.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
          expect(debordement).toBe(false);
        });
      }
    });
  }
