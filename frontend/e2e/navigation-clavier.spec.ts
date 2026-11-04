import { expect, test } from "@playwright/test";

/** Navigation de la coquille au clavier seul (critère « Accessibilité clavier », EPIC 003). */

test.describe("bureau", () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  test("la barre latérale se parcourt à Tab et s'active à Entrée", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { level: 1, name: /Bon retour/ })).toBeVisible();

    const lien = page
      .getByRole("navigation", { name: "Navigation principale" })
      .getByRole("link", { name: "Offres sauvegardées" });
    for (let i = 0; i < 30 && !(await lien.evaluate((el) => el === document.activeElement)); i++) {
      await page.keyboard.press("Tab");
    }
    await expect(lien).toBeFocused();
    await page.keyboard.press("Enter");

    await expect(page).toHaveURL(/\/saved-jobs$/);
    await expect(lien).toHaveAttribute("aria-current", "page");
  });

  test("tout contrôle atteint au clavier a un anneau de focus visible", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { level: 1, name: /Bon retour/ })).toBeVisible();

    for (let i = 0; i < 14; i++) {
      await page.keyboard.press("Tab");
      const focus = await page.evaluate(() => {
        const el = document.activeElement as HTMLElement;
        const css = getComputedStyle(el);
        const visible = css.outlineStyle !== "none" && Number.parseFloat(css.outlineWidth) >= 2;
        // Le lien d'évitement est masqué hors focus : il apparaît justement au focus.
        return {
          visible,
          nom: el.getAttribute("aria-label") ?? el.textContent?.trim() ?? el.tagName,
        };
      });
      expect(focus.visible, `pas d'anneau de focus sur « ${focus.nom} »`).toBe(true);
    }
  });
});

test.describe("mobile", () => {
  test.use({ viewport: { width: 390, height: 800 } });

  test("le tiroir s'ouvre au clavier, garde le focus et se ferme avec Échap", async ({ page }) => {
    await page.goto("/dashboard");
    const ouvrir = page.getByRole("button", { name: "Ouvrir le menu" });
    for (
      let i = 0;
      i < 20 && !(await ouvrir.evaluate((el) => el === document.activeElement));
      i++
    ) {
      await page.keyboard.press("Tab");
    }
    await expect(ouvrir).toBeFocused();
    await page.keyboard.press("Enter");

    const tiroir = page.getByRole("dialog");
    await expect(tiroir).toBeVisible();
    for (let i = 0; i < 14; i++) {
      await page.keyboard.press("Tab");
      const dedans = await page.evaluate(
        () => document.querySelector('[role="dialog"]')?.contains(document.activeElement) ?? false,
      );
      expect(dedans).toBe(true); // le focus ne s'échappe pas vers la page masquée
    }

    await page.keyboard.press("Escape");
    await expect(tiroir).toBeHidden();
    await expect(ouvrir).toBeFocused(); // le focus revient là où l'utilisateur l'avait laissé
  });
});
