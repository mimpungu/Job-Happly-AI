import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { NAVIGATION_ITEMS } from "../src/features/shell/navigation";

const TAILLES = [
  { nom: "mobile", width: 390, height: 800 },
  { nom: "tablette", width: 768, height: 1024 },
  { nom: "bureau", width: 1280, height: 800 },
];

const THEMES = ["dark", "light"] as const;

for (const theme of THEMES) {
  for (const { nom, width, height } of TAILLES) {
    test.describe(`thème ${theme}, écran ${nom}`, () => {
      test.use({ viewport: { width, height } });

      for (const { label, href } of NAVIGATION_ITEMS) {
        test(`« ${label} » : aucune violation d'accessibilité ni débordement`, async ({ page }) => {
          await page.addInitScript((t) => localStorage.setItem("happly-theme", t), theme);
          await page.goto(href);

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

      test("« Recherche d'emploi » : la fenêtre « Tous les filtres » est accessible", async ({
        page,
      }) => {
        await page.addInitScript((t) => localStorage.setItem("happly-theme", t), theme);
        await page.goto("/jobs");
        await page.getByRole("button", { name: /Tous les filtres/ }).click();
        await expect(page.getByRole("dialog", { name: "Tous les filtres" })).toBeVisible();

        const resultat = await new AxeBuilder({ page })
          .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
          .analyze();

        expect(resultat.violations.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
      });
    });
  }
}
