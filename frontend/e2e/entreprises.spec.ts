import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Route } from "@playwright/test";

/**
 * Parcours « entreprises suivies » : recherche par nom libre, suivi, collecte, au clavier.
 * L'API est interceptée : déterministe, sans réseau ni base. La vraie chaîne (API + sites
 * carrières publics) est vérifiée à part, à la main, et décrite dans le compte rendu.
 */

const ORIGINE = "http://127.0.0.1:3100";
const CORS = {
  "access-control-allow-origin": ORIGINE,
  "access-control-allow-methods": "GET,POST,PUT,PATCH,DELETE",
  "access-control-allow-headers": "Content-Type",
};

const suivie = {
  id: "c1",
  name: "Acme Corp",
  careers_url: "https://boards.greenhouse.io/acme",
  ats_kind: "greenhouse",
  detection_status: "supported",
  enabled: true,
  last_checked_at: null,
  last_success_at: null,
  last_error: null,
};

const trouve = {
  ats_kind: "greenhouse",
  token: "acme",
  careers_url: "https://boards.greenhouse.io/acme",
  board_name: "Acme Corp",
  offer_count: 3,
};

const bilan = {
  started_at: "2026-11-03T10:00:00Z",
  finished_at: "2026-11-03T10:00:05Z",
  status: "partial",
  sources: [
    {
      company_id: "c1",
      company_name: "Acme Corp",
      source_key: "greenhouse:acme",
      succeeded: true,
      complete: true,
      fetched: 3,
      created: 3,
      merged: 0,
      changed: 0,
      unchanged: 0,
      rejected: 0,
      expired: 0,
      error_type: null,
    },
    {
      company_id: "c2",
      company_name: "Panne SA",
      source_key: "lever:panne",
      succeeded: false,
      complete: false,
      fetched: 0,
      created: 0,
      merged: 0,
      changed: 0,
      unchanged: 0,
      rejected: 0,
      expired: 0,
      error_type: "SourceUnavailableError",
    },
  ],
};

test("recherche, suivi puis collecte d'une entreprise tapée librement, au clavier", async ({
  page,
}) => {
  let entreprises: unknown[] = [];
  await page.route("**/api/v1/target-companies**", async (route: Route) => {
    const requete = route.request();
    if (requete.method() === "OPTIONS") return route.fulfill({ status: 204, headers: CORS });
    const json = (corps: unknown, status = 200) =>
      route.fulfill({
        status,
        headers: CORS,
        contentType: "application/json",
        body: JSON.stringify(corps),
      });
    if (requete.url().endsWith("/discover")) return json([trouve]);
    if (requete.method() === "POST") {
      entreprises = [suivie];
      return json(suivie, 201);
    }
    return json(entreprises);
  });
  await page.route("**/api/v1/collection/run", async (route: Route) => {
    if (route.request().method() === "OPTIONS")
      return route.fulfill({ status: 204, headers: CORS });
    return route.fulfill({
      status: 200,
      headers: CORS,
      contentType: "application/json",
      body: JSON.stringify(bilan),
    });
  });
  await page.goto("/settings");

  await expect(page.getByText(/Aucune entreprise suivie/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Collecter les offres" })).toBeDisabled();

  // Nom libre : saisi au clavier, validé avec Entrée.
  await page.getByLabel("Nom de l'entreprise").focus();
  await page.keyboard.type("Acme");
  await page.keyboard.press("Enter");
  const trouves = page.getByRole("list", { name: "Sites carrières trouvés" });
  await expect(trouves).toContainText("Acme Corp · Greenhouse");
  await expect(trouves).toContainText("3 offres publiées");

  await page.getByRole("button", { name: /Suivre Acme Corp/ }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("list", { name: "Entreprises suivies" })).toContainText("Acme Corp");
  await expect(page.locator("[data-sonner-toast]").first()).toBeVisible();

  await page.getByRole("button", { name: "Collecter les offres" }).focus();
  await page.keyboard.press("Enter");
  const sources = page.getByRole("list", { name: "Sources interrogées" });
  await expect(sources).toContainText("3 offres lues · 3 nouvelles");
  await expect(sources).toContainText("Source indisponible ou refusée");

  // Les toasts s'estompent pendant l'audit : on attend leur disparition (cause connue d'un
  // faux positif de contraste pendant le fondu).
  await expect(page.locator("[data-sonner-toast]")).toHaveCount(0, { timeout: 15_000 });
  const resultat = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(resultat.violations.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
});

test("une entreprise sans site carrières reconnu est expliquée, pas déclarée sans offres", async ({
  page,
}) => {
  await page.route("**/api/v1/target-companies**", async (route: Route) => {
    if (route.request().method() === "OPTIONS")
      return route.fulfill({ status: 204, headers: CORS });
    const corps = route.request().url().endsWith("/discover") ? [] : [];
    return route.fulfill({
      status: 200,
      headers: CORS,
      contentType: "application/json",
      body: JSON.stringify(corps),
    });
  });
  await page.goto("/settings");

  await page.getByLabel("Nom de l'entreprise").fill("Inconnue");
  await page.getByRole("button", { name: "Chercher" }).click();

  await expect(page.getByRole("status")).toContainText("ne veut pas dire");
});
