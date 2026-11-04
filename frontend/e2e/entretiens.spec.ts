import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { candidature } from "../src/features/applications/fixtures";

const TAILLES = [
  { nom: "mobile", width: 390, height: 800 },
  { nom: "tablette", width: 768, height: 1024 },
  { nom: "bureau", width: 1280, height: 800 },
];
const THEMES = ["dark", "light"] as const;

const question = {
  id: "technical-1",
  category: "technical",
  text: "Décrivez un cas concret où vous avez utilisé Python.",
  rationale: "Compétence demandée par l'offre et présente dans votre profil.",
  skill: "Python",
  skill_gap: false,
  source: "rules",
};

const preparation = {
  id: "p1",
  application_id: "c1",
  content: {
    questions: [
      question,
      {
        ...question,
        id: "technical-2",
        text: "Comment aborderiez-vous Kubernetes ?",
        skill: "Kubernetes",
        skill_gap: true,
      },
    ],
    pitch: "Je m'appelle Camille Dubois. [À compléter : votre motivation.]",
    pitch_to_complete: ["[À compléter : votre motivation.]"],
    highlights: [
      {
        experience_label: "Ingénieure — OpenCorp",
        matched_terms: ["Python"],
        achievements: ["Migration FastAPI"],
      },
    ],
    answers: [
      {
        question_id: "technical-1",
        experience_label: "Ingénieure — OpenCorp",
        situation: "Ingénieure — OpenCorp (2021 - aujourd'hui)",
        actions: ["Migration FastAPI"],
        result: null,
        to_complete: ["Résultat réel de cette réalisation"],
      },
    ],
    recruiter_questions: ["Comment se passe l'intégration ?"],
    skills_matched: ["Python"],
    skills_to_prepare: ["Kubernetes"],
    warnings: ["Offre non analysée : questions limitées."],
  },
  meta: {
    language: "fr",
    cv_version_id: null,
    ai: { requested: "ai", status: "unavailable", reason: "Plafond atteint." },
  },
  created_at: "2026-11-04T10:00:00Z",
  updated_at: "2026-11-04T10:00:00Z",
};

const simulation = {
  id: "s1",
  application_id: "c1",
  status: "completed",
  questions: [question],
  answers: [
    {
      question_id: "technical-1",
      text: "Dans mon poste, j'ai migré 12 services.",
      answered_at: "2026-11-04T10:05:00Z",
      feedback: {
        score: 72,
        strengths: ["Longueur adaptée."],
        improvements: ["Ajoutez un élément concret."],
        unverified_numbers: [],
        ai_comments: [],
        ai_status: "unavailable",
      },
    },
  ],
  summary: {
    answered: 1,
    total: 1,
    average_score: 72,
    best_question_id: "technical-1",
    weakest_question_id: null,
    unanswered: [],
  },
  created_at: "2026-11-04T10:00:00Z",
  completed_at: "2026-11-04T10:06:00Z",
};

const entretien = {
  id: "i1",
  application_id: "c1",
  stage: "technical",
  format: "video",
  scheduled_at: "2026-11-10T09:00:00Z",
  location: "Visio",
  interviewers: ["Marie"],
  notes: "Revoir l'architecture.",
  outcome: "pending",
  feedback_notes: null,
  follow_up_draft: {
    subject: "Merci pour notre échange",
    body: "Bonjour Marie,\n\nMerci. [À compléter : un point précis]",
    suggested_follow_up_at: "2026-11-12T09:00:00Z",
  },
  created_at: "2026-11-04T10:00:00Z",
  updated_at: "2026-11-04T10:00:00Z",
};

async function simulerApi(page: Page) {
  await page.route("**/api/v1/**", async (route) => {
    const { pathname } = new URL(route.request().url());
    const corps = (() => {
      if (pathname.endsWith("/preparation")) return preparation;
      if (pathname.endsWith("/simulations")) return [simulation];
      if (pathname.endsWith("/interviews")) return [entretien];
      return { items: [candidature()], total: 1, limit: 25, offset: 0 };
    })();
    await route.fulfill({ json: corps });
  });
}

for (const theme of THEMES)
  for (const { nom: ecran, width, height } of TAILLES) {
    test.describe(`thème ${theme}, écran ${ecran}`, () => {
      test.use({ viewport: { width, height } });

      for (const onglet of ["Préparation", "Simulation", "Entretiens"]) {
        test(`onglet « ${onglet} » : aucune violation d'accessibilité ni débordement`, async ({
          page,
        }) => {
          await page.addInitScript((t) => localStorage.setItem("happly-theme", t), theme);
          await simulerApi(page);
          await page.goto("/interview-preparation?application=c1");
          await page.getByRole("tab", { name: onglet }).click();
          if (onglet === "Simulation")
            await page.getByRole("button", { name: "Ouvrir", exact: true }).click();
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
