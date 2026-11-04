import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const TAILLES = [
  { nom: "mobile", width: 390, height: 800 },
  { nom: "tablette", width: 768, height: 1024 },
  { nom: "bureau", width: 1280, height: 800 },
];
const THEMES = ["dark", "light"] as const;

const privacy: Record<string, unknown> = {
  "/api/v1/privacy/summary": [
    {
      category: "profile",
      label: "Profil maître (identité, expériences, formations, compétences)",
      rows: 12,
      file_bytes: 0,
      tables: {},
    },
    {
      category: "documents",
      label: "CV et lettres générés (versions et fichiers PDF)",
      rows: 4,
      file_bytes: 2_500_000,
      tables: {},
    },
  ],
  "/api/v1/privacy/retention": [
    {
      table: "ai_cache_entries",
      category: "ai_activity",
      days: 30,
      description: "Réponses IA mises en cache",
      automatic: true,
    },
    {
      table: "applications",
      category: "applications",
      days: null,
      description: "Candidatures et historique",
      automatic: false,
    },
  ],
  "/api/v1/privacy/ai-transfers": [
    {
      task_type: "cv_rewrite",
      purpose: "Reformuler les réalisations d'un CV",
      data_sent: "Texte des réalisations",
      never_sent: "Identité, CV complet",
      personal_data: true,
      optional: true,
    },
  ],
  "/api/v1/privacy/settings": { personal_data_policy: "allowed", confirmation_word: "SUPPRIMER" },
  "/api/v1/health/details": {
    status: "degraded",
    components: [
      { name: "database", status: "ok", detail: null, data: {} },
      { name: "ai", status: "not_configured", detail: "Aucun fournisseur IA configuré.", data: {} },
      { name: "tasks", status: "degraded", detail: "2 tâche(s) en retard", data: {} },
      { name: "latex", status: "down", detail: "pdfLaTeX introuvable.", data: {} },
    ],
  },
  "/api/v1/health/metrics": {
    uptime_seconds: 3600,
    requests: 42,
    server_errors: 1,
    rate_limited: 0,
    routes: { "GET /api/v1/x": { count: 3, errors: 0, avg_ms: 5, p50_ms: 4, p95_ms: 9 } },
  },
};

async function simulerApi(page: Page) {
  await page.route("**/api/v1/**", async (route) => {
    const { pathname } = new URL(route.request().url());
    const corps = privacy[pathname];
    if (corps !== undefined) return route.fulfill({ json: corps });
    // Les autres panneaux des paramètres ne sont pas l'objet de ce test.
    return route.fulfill({
      status: 503,
      json: { error: { code: "indisponible", message: "Service indisponible." } },
    });
  });
}

for (const theme of THEMES)
  for (const { nom, width, height } of TAILLES) {
    test.describe(`thème ${theme}, écran ${nom}`, () => {
      test.use({ viewport: { width, height } });

      test("Paramètres : confidentialité et santé sans violation d'accessibilité", async ({
        page,
      }) => {
        await page.addInitScript((t) => localStorage.setItem("happly-theme", t), theme);
        await simulerApi(page);
        await page.goto("/settings");
        await expect(page.getByText(/12 ligne\(s\)/)).toBeVisible();
        await expect(page.getByText("Opérationnel").first()).toBeVisible();
        await page.getByText("Ce qui peut être envoyé à un fournisseur d'IA").click();

        const resultat = await new AxeBuilder({ page })
          .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
          .analyze();
        const debordement = await page.evaluate(
          () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
        );

        expect(resultat.violations.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
        expect(debordement).toBe(false);
      });
    });
  }

test("la suppression se confirme au clavier et le focus revient au déclencheur", async ({
  page,
}) => {
  await simulerApi(page);
  await page.goto("/settings");
  const declencheur = page.getByRole("button", { name: "Tout supprimer" });
  await declencheur.focus();
  await page.keyboard.press("Enter");

  const dialogue = page.getByRole("dialog", { name: "Suppression définitive" });
  await expect(dialogue).toBeVisible();
  await expect(dialogue.getByRole("button", { name: "Supprimer définitivement" })).toBeDisabled();
  const resultat = await new AxeBuilder({ page })
    .include('[role="dialog"]')
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(resultat.violations.map((v) => `${v.id}: ${v.help}`)).toEqual([]);

  await page.keyboard.press("Escape");
  await expect(dialogue).toBeHidden();
  await expect(declencheur).toBeFocused();
});
