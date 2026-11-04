import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * Parcours du profil au clavier seul. L'API est interceptée : le test est déterministe et ne
 * dépend ni du backend ni d'une base. Seule la boîte de dialogue de fichier du système reste
 * pilotée par Playwright (elle ne peut pas être automatisée au clavier).
 */

const ORIGINE = "http://127.0.0.1:3100";
const CORS = {
  "access-control-allow-origin": ORIGINE,
  "access-control-allow-methods": "GET,POST,PUT,PATCH,DELETE",
  "access-control-allow-headers": "Content-Type",
};

const element = {
  id: null,
  origin: "imported",
  validated: false,
};

const proposition = {
  identity: {
    first_name: "Marie",
    last_name: "Dupont",
    email: null,
    phone: null,
    city: null,
    country_code: null,
    headline: null,
  },
  summary: null,
  experiences: [
    {
      ...element,
      source_text: "Développeuse Python\n2021 - Aujourd'hui",
      title: "Développeuse Python",
      company: null,
      location: null,
      start: { year: 2021, month: null },
      end: null,
      is_current: true,
      description: null,
      achievements: [],
    },
  ],
  educations: [],
  skills: [],
  languages: [],
  certifications: [],
  preferences: {
    job_titles: [],
    country_codes: [],
    cities: [],
    remote_types: [],
    employment_types: [],
    salary_min: null,
    salary_currency: null,
    application_languages: [],
  },
};

async function simulerApi(page: Page) {
  await page.route("**/api/v1/profile**", async (route: Route) => {
    const requete = route.request();
    if (requete.method() === "OPTIONS") {
      return route.fulfill({ status: 204, headers: CORS });
    }
    const json = (corps: unknown, status = 200) =>
      route.fulfill({
        status,
        headers: { ...CORS, "content-type": "application/json" },
        body: JSON.stringify(corps),
      });
    const { pathname } = new URL(requete.url());
    if (pathname.endsWith("/import")) {
      return json({
        filename: "cv.txt",
        format: "txt",
        page_count: null,
        warnings: [],
        text: "…",
        proposed_document: proposition,
      });
    }
    return json(null); // GET /profile : aucun profil
  });
}

/** Avance au clavier jusqu'à l'élément voulu ; échoue si on ne l'atteint pas (piège à focus). */
// Garde-fou contre une boucle infinie : un tour complet de la page (coque comprise) doit tenir.
async function tabJusqua(page: Page, nom: RegExp | string, max = 120) {
  for (let i = 0; i < max; i++) {
    await page.keyboard.press("Tab");
    const actif = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      if (!el) return "";
      const etiquette = el.getAttribute("aria-label");
      const labels = (el as HTMLInputElement).labels;
      // Le texte n'est un nom que pour un vrai contrôle : une zone focusable (panneau d'onglet)
      // contient le texte de tous ses descendants et ne doit pas être prise pour l'un d'eux.
      const porteSonTexte = ["BUTTON", "A", "SUMMARY"].includes(el.tagName);
      return (
        etiquette ??
        (labels && labels[0]?.textContent) ??
        (porteSonTexte ? el.textContent : "") ??
        ""
      )
        .trim()
        .replace(/\s+/g, " ");
    });
    if (typeof nom === "string" ? actif === nom : nom.test(actif)) return;
  }
  throw new Error(`Élément « ${String(nom)} » inaccessible au clavier`);
}

/**
 * Entrée au clavier sur le bouton d'import, jusqu'à ce que le sélecteur de fichier s'ouvre.
 * En mode développement, la page peut être visible avant d'être hydratée : une touche pressée
 * trop tôt est perdue. On réessaie la touche, jamais un clic (le parcours reste au clavier).
 */
async function entrerPourChoisirUnFichier(page: Page) {
  for (let essai = 0; essai < 6; essai++) {
    const attente = page.waitForEvent("filechooser", { timeout: 4000 }).catch(() => null);
    await page.keyboard.press("Enter");
    const selecteur = await attente;
    if (selecteur) return selecteur;
  }
  throw new Error("Le sélecteur de fichier ne s'ouvre pas au clavier");
}

test.beforeEach(async ({ page }) => {
  await simulerApi(page);
});

test("le lien d'évitement mène au contenu principal", async ({ page }) => {
  await page.goto("/cv-studio");
  await expect(page.getByText("Aucun CV maître")).toBeVisible();

  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Aller au contenu" })).toBeFocused();
  await page.keyboard.press("Enter");

  await expect(page).toHaveURL(/#contenu$/);
});

test("anneau de focus visible et mouvement réduit respecté", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/cv-studio");
  await expect(page.getByText("Aucun CV maître")).toBeVisible();

  await tabJusqua(page, "Importer un CV");

  const style = await page.evaluate(() => {
    const css = getComputedStyle(document.activeElement as Element);
    return { style: css.outlineStyle, largeur: css.outlineWidth };
  });
  expect(style.style).not.toBe("none");
  expect(style.largeur).toBe("2px");
  const transition = await page.evaluate(
    () => getComputedStyle(document.querySelector("button") as Element).transitionDuration,
  );
  expect(Number.parseFloat(transition)).toBeLessThan(0.001);
});

test("importer, relire, compléter et confirmer un élément sans souris", async ({ page }) => {
  await page.goto("/cv-studio");
  await expect(page.getByText("Aucun CV maître")).toBeVisible();

  // Le bouton d'import s'active au clavier et ouvre le sélecteur de fichier du système.
  await tabJusqua(page, "Importer un CV");
  const selecteur = await entrerPourChoisirUnFichier(page);
  await selecteur.setFiles({ name: "cv.txt", mimeType: "text/plain", buffer: Buffer.from("x") });
  await expect(page.getByText("1 élément à confirmer")).toBeVisible();

  // Les onglets se parcourent aux flèches.
  await page.getByRole("tab", { name: "Identité" }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: /Expériences/ })).toHaveAttribute(
    "aria-selected",
    "true",
  );

  // La confirmation est impossible tant qu'il manque l'entreprise (état annoncé au clavier aussi).
  const confirmer = page.getByRole("button", { name: /Confirmer : Développeuse Python/ });
  await expect(confirmer).toBeDisabled();

  await tabJusqua(page, "Entreprise");
  await page.keyboard.type("Exemple SA");
  await expect(confirmer).toBeEnabled();
  await tabJusqua(page, /Confirmer : Développeuse Python/);
  await page.keyboard.press("Space");

  await expect(page.getByText("Confirmé", { exact: true })).toBeVisible();
  await expect(page.getByText("À confirmer", { exact: true })).toHaveCount(0);
});

test("l'extrait source se déplie au clavier", async ({ page }) => {
  await page.goto("/cv-studio");
  await expect(page.getByText("Aucun CV maître")).toBeVisible();
  await tabJusqua(page, "Importer un CV");
  const selecteur = await entrerPourChoisirUnFichier(page);
  await selecteur.setFiles({ name: "cv.txt", mimeType: "text/plain", buffer: Buffer.from("x") });
  await expect(page.getByText("1 élément à confirmer")).toBeVisible();
  await page.getByRole("tab", { name: /Expériences/ }).click();

  await tabJusqua(page, /Voir l'extrait du CV d'origine/);
  await page.keyboard.press("Enter");

  await expect(page.getByText(/Développeuse Python\s+2021/)).toBeVisible();
});

test("la fenêtre de confirmation piège le focus et se ferme avec Échap", async ({ page }) => {
  await page.goto("/cv-studio");
  await expect(page.getByText("Aucun CV maître")).toBeVisible();
  await tabJusqua(page, "Importer un CV");
  let selecteur = await entrerPourChoisirUnFichier(page);
  await selecteur.setFiles({ name: "cv.txt", mimeType: "text/plain", buffer: Buffer.from("x") });
  await expect(page.getByText("1 élément à confirmer")).toBeVisible();

  // Un second import, alors que le brouillon a du contenu, demande confirmation.
  await tabJusqua(page, "Importer un CV");
  selecteur = await entrerPourChoisirUnFichier(page);
  await selecteur.setFiles({ name: "cv.txt", mimeType: "text/plain", buffer: Buffer.from("x") });
  const dialogue = page.getByRole("dialog", { name: "Remplacer le brouillon par ce CV ?" });
  await expect(dialogue).toBeVisible();

  for (let i = 0; i < 8; i++) {
    await page.keyboard.press("Tab");
    const dedans = await page.evaluate(
      () => document.querySelector('[role="dialog"]')?.contains(document.activeElement) ?? false,
    );
    expect(dedans).toBe(true); // le focus ne sort jamais de la fenêtre
  }

  await page.keyboard.press("Escape");
  await expect(dialogue).toHaveCount(0);
});
