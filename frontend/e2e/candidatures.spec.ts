import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import {
  candidature,
  dashboard,
  detail,
  dossier,
  stats,
} from "../src/features/applications/fixtures";
import { APPLICATION_STATUSES } from "../src/types/application-status";

const TAILLES = [
  { nom: "mobile", width: 390, height: 800 },
  { nom: "tablette", width: 768, height: 1024 },
  { nom: "bureau", width: 1280, height: 800 },
];

/** API locale simulée avec des données : on vérifie les écrans réels, pas seulement l'état d'erreur. */
async function simulerApi(page: Page) {
  await page.route("**/api/v1/**", async (route) => {
    const { pathname } = new URL(route.request().url());
    const corps = (() => {
      if (pathname.endsWith("/dashboard")) return dashboard();
      if (pathname.endsWith("/applications/stats")) return stats();
      if (pathname.endsWith("/applications/kanban"))
        return {
          columns: APPLICATION_STATUSES.map((status) => {
            const items =
              status === "to_apply"
                ? [candidature(), candidature({ id: "c2" })]
                : status === "sent"
                  ? [candidature({ id: "c3", status: "sent", applied_at: "2026-11-03T12:00:00Z" })]
                  : [];
            return {
              status,
              count: items.length + (status === "to_apply" ? 5 : 0),
              items,
              has_more: status === "to_apply",
            };
          }),
        };
      if (pathname.endsWith("/applications"))
        return {
          items: [candidature(), candidature({ id: "c2", status: "sent" })],
          total: 2,
          limit: 25,
          offset: 0,
        };
      if (pathname.endsWith("/dossier")) return dossier();
      if (pathname.endsWith("/resumes") || pathname.endsWith("/cover-letters")) return [];
      return detail();
    })();
    await route.fulfill({ json: corps });
  });
}

const PAGES = [
  { nom: "tableau de bord", chemin: "/dashboard", titre: /Bon retour/ },
  { nom: "candidatures (tableau)", chemin: "/applications", titre: "Candidatures" },
  { nom: "candidatures (Kanban)", chemin: "/applications?vue=kanban", titre: "Candidatures" },
  { nom: "fiche d'une candidature", chemin: "/applications/c1", titre: "Développeur Python" },
];

const THEMES = ["dark", "light"] as const;

for (const theme of THEMES)
  for (const { nom: ecran, width, height } of TAILLES) {
    test.describe(`thème ${theme}, écran ${ecran}`, () => {
      test.use({ viewport: { width, height } });

      for (const { nom, chemin, titre } of PAGES) {
        test(`« ${nom} » avec données : aucune violation d'accessibilité ni débordement`, async ({
          page,
        }) => {
          await page.addInitScript((t) => localStorage.setItem("happly-theme", t), theme);
          await simulerApi(page);
          await page.goto(chemin);
          await expect(page.getByRole("heading", { level: 1, name: titre })).toBeVisible();
          // Les données sont affichées : l'état de chargement ne doit plus être audité.
          await expect(page.getByRole("status")).toHaveCount(0);

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

test("la confirmation d'envoi s'utilise au clavier et rappelle que rien n'est envoyé", async ({
  page,
}) => {
  await simulerApi(page);
  await page.goto("/applications/c1");

  const bouton = page.getByRole("button", { name: "J'ai envoyé ma candidature" });
  await bouton.focus();
  await page.keyboard.press("Enter");

  const dialogue = page.getByRole("dialog", { name: "Confirmer l'envoi" });
  await expect(dialogue).toBeVisible();
  await expect(dialogue).toContainText("n'envoie jamais rien à votre place");
  const resultat = await new AxeBuilder({ page })
    .include('[role="dialog"]')
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(resultat.violations.map((v) => `${v.id}: ${v.help}`)).toEqual([]);

  await page.keyboard.press("Escape");
  await expect(dialogue).toBeHidden();
  await expect(bouton).toBeFocused(); // le focus revient là d'où l'on vient
});

test("le Kanban reste navigable au clavier jusqu'à une fiche", async ({ page }) => {
  await simulerApi(page);
  await page.goto("/applications?vue=kanban");

  const colonne = page.getByRole("region", { name: /À postuler/ });
  await expect(colonne).toBeVisible();
  await colonne.getByRole("link", { name: "Développeur Python" }).first().focus();
  await page.keyboard.press("Enter");

  await expect(page).toHaveURL(/\/applications\/c1$/);
});
