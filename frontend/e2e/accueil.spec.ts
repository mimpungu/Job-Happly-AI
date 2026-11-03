import { expect, test } from "@playwright/test";

test("la page d'accueil affiche Happly AI", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Happly AI" })).toBeVisible();
});
