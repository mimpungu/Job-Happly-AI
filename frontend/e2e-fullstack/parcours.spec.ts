import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

/**
 * Parcours métier principaux, de bout en bout : navigateur → API → PostgreSQL → pdfLaTeX.
 * Ils s'enchaînent comme le ferait un candidat : chaque étape s'appuie sur la précédente.
 */
test.describe.configure({ mode: "serial" });

const OFFRE = {
  titre: "Ingénieure Backend Python",
  entreprise: "Acme Données",
  lieu: "Lyon, France",
  url: "https://careers.exemple.test/ingenieure-backend",
  texte:
    "Acme Données recrute une ingénieure backend pour construire sa plateforme de données.\n\n" +
    "Missions : concevoir des API REST, maintenir PostgreSQL, améliorer la fiabilité.\n\n" +
    "Compétences requises : Python, PostgreSQL, Docker. CDI, Lyon, télétravail partiel.",
};

async function confirmerToutesLesLignes(page: Page) {
  // Chaque élément importé reste « à confirmer » tant que l'utilisateur ne l'a pas relu, section
  // par section ; une langue sans niveau reconnu demande un choix explicite (jamais deviné).
  for (const onglet of [
    /^Expériences/,
    /^Formations/,
    /^Compétences/,
    /^Langues et certifications/,
  ]) {
    await page.getByRole("tab", { name: onglet }).click();
    const niveaux = page.getByLabel("Niveau");
    for (let i = 0; i < (await niveaux.count()); i++) {
      if ((await niveaux.nth(i).inputValue()) === "")
        await niveaux.nth(i).selectOption({ index: 3 });
    }
    for (let garde = 0; garde < 40; garde++) {
      const bouton = page.getByRole("button", { name: /^Confirmer : / }).first();
      if (!(await bouton.isVisible().catch(() => false))) break;
      await bouton.click();
    }
  }
}

test("1. import du CV : lecture locale, relecture, enregistrement et validation du profil", async ({
  page,
}) => {
  await page.goto("/cv-studio");
  await expect(page.getByRole("heading", { level: 1, name: "Espace CV" })).toBeVisible();
  await expect(page.getByText("Aucun CV maître")).toBeVisible();

  await page
    .getByLabel("Fichier du CV à importer")
    .setInputFiles(path.join(__dirname, "fixtures", "cv-marie-dupont.txt"));
  await expect(page.getByText(/CV lu/).first()).toBeVisible();
  await expect(page.getByText(/à confirmer/).first()).toBeVisible();

  await confirmerToutesLesLignes(page);
  await page.getByRole("button", { name: "Enregistrer", exact: true }).click();
  await expect(page.getByText("Brouillon enregistré.")).toBeVisible();

  await page.getByRole("button", { name: "Valider le profil" }).click();
  await expect(page.getByText("Profil validé.")).toBeVisible();
  await expect(page.getByText(/Version 1 · validée/)).toBeVisible();
});

test("2. recherche : ajout d'une offre depuis son texte puis recherche par mot-clé", async ({
  page,
}) => {
  await page.goto("/jobs");
  await page.getByRole("button", { name: "Ajouter une offre" }).first().click();
  const dialogue = page.getByRole("dialog", { name: "Ajouter une offre" });
  await dialogue.getByLabel("Intitulé du poste").fill(OFFRE.titre);
  await dialogue.getByLabel(/Entreprise/).fill(OFFRE.entreprise);
  await dialogue.getByLabel(/Lieu/).fill(OFFRE.lieu);
  await dialogue.getByLabel("Adresse de l'offre").fill(OFFRE.url);
  await dialogue.getByLabel("Texte de l'offre").fill(OFFRE.texte);
  await dialogue.getByRole("button", { name: "Ajouter", exact: true }).click();
  await dialogue.getByRole("button", { name: "Fermer" }).first().click();

  await page.goto("/jobs");
  await expect(page.getByRole("link", { name: OFFRE.titre })).toBeVisible();

  await page.goto("/jobs?text=PostgreSQL");
  await expect(page.getByRole("link", { name: OFFRE.titre })).toBeVisible();
  await page.goto("/jobs?text=introuvableXYZ");
  // un état vide explicite, pas seulement l'absence de lien (qui serait vraie pendant le chargement)
  await expect(page.getByText("Aucune offre ne correspond")).toBeVisible();
  await expect(page.getByRole("link", { name: OFFRE.titre })).toHaveCount(0);
});

test("3. génération du CV ciblé : audit ATS, PDF et LaTeX téléchargeables", async ({ page }) => {
  await page.goto("/cv-studio");
  await page.getByRole("tab", { name: "CV générés" }).click();
  await expect(page.getByText("Aucun CV généré")).toBeVisible();

  await page
    .getByLabel(/Offre ciblée/)
    .selectOption({ label: `${OFFRE.titre} — ${OFFRE.entreprise}` });
  await page.getByRole("button", { name: "Générer le CV" }).click();

  await expect(page.getByText("CV généré.")).toBeVisible();
  await expect(page.getByText(/ATS \d+\/100/)).toBeVisible();
  const pdf = page.getByRole("link", { name: /Télécharger le PDF/ }).first();
  const reponse = await page.request.get((await pdf.getAttribute("href")) as string);
  expect(reponse.status()).toBe(200);
  expect(reponse.headers()["content-type"]).toBe("application/pdf");
  expect((await reponse.body()).subarray(0, 5).toString()).toBe("%PDF-");
  const latex = page.getByRole("link", { name: /Télécharger le source LaTeX/ }).first();
  const source = await page.request.get((await latex.getAttribute("href")) as string);
  expect(await source.text()).toContain("\\documentclass");
  // aucun fait inventé : la compétence de l'offre absente du profil n'est jamais ajoutée au CV
  expect(await source.text()).not.toContain("Docker, Git");
});

test("4. génération de la lettre : audit, relecture avant envoi, PDF", async ({ page }) => {
  await page.goto("/cover-letters");
  await expect(page.getByText("Aucune lettre")).toBeVisible();

  await page
    .getByLabel(/Offre ciblée/)
    .selectOption({ label: `${OFFRE.titre} — ${OFFRE.entreprise}` });
  await page
    .getByLabel(/Votre motivation/)
    .fill("Votre plateforme de données me motive particulièrement.");
  await page.getByRole("button", { name: "Générer la lettre" }).click();

  await expect(page.getByText("Lettre générée.")).toBeVisible();
  await expect(page.getByText(/Qualité \d+\/100/)).toBeVisible();
  await expect(page.getByText("Cohérente avec le CV")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Relire la lettre avant envoi" })).toBeVisible();
  // le texte de l'utilisateur est repris tel quel dans la lettre
  await expect(
    page
      .getByRole("region", { name: "Relire la lettre avant envoi" })
      .getByText("Votre plateforme de données me motive particulièrement."),
  ).toBeVisible();
  const pdf = page.getByRole("link", { name: /Télécharger le PDF/ }).first();
  const reponse = await page.request.get((await pdf.getAttribute("href")) as string);
  expect(reponse.headers()["content-type"]).toBe("application/pdf");
});

test("5. candidature : suivi de l'offre, documents, confirmation d'envoi manuelle", async ({
  page,
}) => {
  await page.goto("/jobs");
  await page.getByRole("link", { name: OFFRE.titre }).click();
  await page.getByRole("button", { name: "Suivre cette candidature" }).click();
  await expect(page).toHaveURL(/\/applications\/[0-9a-f-]{36}$/);
  await expect(page.getByRole("heading", { level: 1, name: OFFRE.titre })).toBeVisible();
  await expect(page.getByText(/Pas encore envoyée/)).toBeVisible();

  // l'application n'envoie jamais rien : l'utilisateur confirme un envoi fait de son côté
  await page.getByRole("button", { name: "J'ai envoyé ma candidature" }).click();
  const dialogue = page.getByRole("dialog", { name: "Confirmer l'envoi" });
  await expect(dialogue).toContainText("n'envoie jamais rien à votre place");
  await dialogue.getByRole("button", { name: /Confirmer que je l'ai envoyée/ }).click();
  await expect(page.getByText(/Envoyée le/)).toBeVisible();

  await page.goto("/applications");
  await expect(page.getByText(OFFRE.titre).first()).toBeVisible();
});

test("6. budget IA : plafonds obligatoires, consentement explicite, aucun appel payant sans eux", async ({
  page,
}) => {
  await page.goto("/ai-center");
  await expect(page.getByText(/Aucun appel payant possible/).first()).toBeVisible();

  await page.getByLabel(/Plafond journalier/).fill("1");
  await page.getByLabel(/Plafond mensuel/).fill("10");
  await page.getByRole("button", { name: "Enregistrer les plafonds" }).click();
  await expect(page.getByText("Plafonds enregistrés.")).toBeVisible();

  await page.reload();
  await expect(page.getByLabel(/Plafond journalier/)).toHaveValue(/^1([.,]00)?$/);
  await expect(page.getByLabel(/Plafond mensuel/)).toHaveValue(/^10([.,]00)?$/);

  await expect(page.getByText("Envoi à l'API non accepté")).toBeVisible();
  await page.getByRole("button", { name: "J'accepte l'envoi de ces données" }).click();
  await expect(page.getByText("Envoi à l'API accepté")).toBeVisible();
  // sans fournisseur payant configuré, aucun appel payant n'est possible malgré plafonds et accord
  await expect(page.getByText(/Aucun appel payant possible/).first()).toBeVisible();
});

test("7. préparation d'entretien : questions adaptées au poste et au vrai parcours, sans IA", async ({
  page,
}) => {
  await page.goto("/applications");
  await page.getByRole("link", { name: OFFRE.titre }).first().click();
  await page.getByRole("link", { name: "Préparer l'entretien" }).click();
  await expect(page).toHaveURL(/\/interview-preparation\?application=/);

  await expect(page.getByText("Aucune préparation")).toBeVisible();
  await page.getByRole("button", { name: "Préparer l'entretien" }).click();

  await expect(page.getByRole("heading", { name: "Présentation personnelle" })).toBeVisible();
  // le parcours vient du profil validé (Marie Dupont), jamais inventé
  await expect(page.getByText(/Marie Dupont/).first()).toBeVisible();
  await expect(page.getByText(/Décrivez un cas concret où vous avez utilisé Python/)).toBeVisible();
  await expect(page.getByText(/À compléter/).first()).toBeVisible();
});

test("8. confidentialité : l'export contient les données, l'effacement exige la confirmation", async ({
  page,
}) => {
  await page.goto("/settings");
  await expect(page.getByText(/ligne\(s\)/).first()).toBeVisible();

  const lien = page.getByRole("link", { name: /Exporter mes données/ });
  const archive = await page.request.get((await lien.getAttribute("href")) as string);
  expect(archive.status()).toBe(200);
  expect(archive.headers()["content-type"]).toBe("application/zip");
  expect((await archive.body()).subarray(0, 2).toString()).toBe("PK");

  await page.getByRole("button", { name: "Tout supprimer" }).click();
  const dialogue = page.getByRole("dialog", { name: "Suppression définitive" });
  await expect(dialogue.getByRole("button", { name: "Supprimer définitivement" })).toBeDisabled();
  await dialogue.getByRole("button", { name: "Annuler" }).click();
  await expect(dialogue).toBeHidden();
});

test("9. mode démonstration : refusé tant que des données réelles existent, jamais mêlé au réel", async ({
  page,
}) => {
  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "Mode démonstration" })).toBeVisible();
  await expect(page.getByText("Inactif")).toBeVisible();

  await page.getByRole("button", { name: "Activer le mode démonstration" }).click();

  await expect(
    page.getByText(/n'est disponible que sans offre ni candidature réelle/),
  ).toBeVisible();
  await expect(page.getByText("Inactif")).toBeVisible();
  await expect(page.getByText("Mode démonstration actif")).toHaveCount(0);
});
