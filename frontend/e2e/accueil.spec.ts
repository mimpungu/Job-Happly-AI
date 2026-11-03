import { expect, test } from "@playwright/test";

import { NAVIGATION_ITEMS } from "../src/features/shell/navigation";

test("la racine redirige vers le tableau de bord", async ({ page }) => {
  await page.goto("/");

  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { level: 1, name: "Tableau de bord" })).toBeVisible();
});

test.describe("navigation (bureau)", () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  for (const { label, href } of NAVIGATION_ITEMS) {
    test(`ouvre la section « ${label} »`, async ({ page }) => {
      await page.goto("/dashboard");

      await page
        .getByRole("navigation", { name: "Navigation principale" })
        .getByRole("link", { name: label })
        .click();

      await expect(page).toHaveURL(new RegExp(`${href}$`));
      await expect(page.getByRole("heading", { level: 1, name: label })).toBeVisible();
      await expect(
        page
          .getByRole("navigation", { name: "Navigation principale" })
          .getByRole("link", { name: label }),
      ).toHaveAttribute("aria-current", "page");
    });
  }

  test("la recherche globale ouvre la page de recherche avec le terme", async ({ page }) => {
    await page.goto("/dashboard");

    await page.getByRole("searchbox", { name: "Recherche globale" }).fill("data analyst");
    await page.keyboard.press("Enter");

    await expect(page).toHaveURL(/\/jobs\?q=data%20analyst$/);
  });
});

test.describe("navigation (mobile)", () => {
  test.use({ viewport: { width: 390, height: 800 } });

  test("la barre latérale est remplacée par un tiroir", async ({ page }) => {
    await page.goto("/dashboard");

    await expect(page.getByRole("navigation", { name: "Navigation principale" })).toBeHidden();
    await page.getByRole("button", { name: "Ouvrir le menu" }).click();
    await page
      .getByRole("navigation", { name: "Navigation principale" })
      .getByRole("link", { name: "Candidatures" })
      .click();

    await expect(page).toHaveURL(/\/applications$/);
    await expect(page.getByRole("dialog")).toBeHidden();
  });

  test("n'a pas de défilement horizontal", async ({ page }) => {
    await page.goto("/dashboard");

    const debordement = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    );

    expect(debordement).toBe(false);
  });
});
