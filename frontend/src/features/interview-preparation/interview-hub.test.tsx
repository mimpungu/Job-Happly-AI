import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Toaster } from "@/components/ui/toaster";
import { candidature, erreurApi, json } from "@/features/applications/fixtures";
import type { Interview, InterviewQuestion, Preparation, Simulation } from "@/types/interviews";

const replace = vi.fn();
let recherche = "application=c1";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => "/interview-preparation",
  useSearchParams: () => new URLSearchParams(recherche),
}));

import { InterviewHub } from "./interview-hub";

const question = (surcharge: Partial<InterviewQuestion> = {}): InterviewQuestion => ({
  id: "technical-1",
  category: "technical",
  text: "Décrivez un cas concret où vous avez utilisé Python.",
  rationale: "Compétence demandée par l'offre et présente dans votre profil.",
  skill: "Python",
  skill_gap: false,
  source: "rules",
  ...surcharge,
});

const preparation = (surcharge: Partial<Preparation["content"]> = {}): Preparation => ({
  id: "p1",
  application_id: "c1",
  content: {
    questions: [
      question(),
      question({
        id: "technical-2",
        text: "Comment aborderiez-vous Kubernetes ?",
        skill: "Kubernetes",
        skill_gap: true,
      }),
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
    warnings: [],
    ...surcharge,
  },
  meta: { language: "fr", cv_version_id: null, ai: { requested: "none", status: "not_requested" } },
  created_at: "2026-11-04T10:00:00Z",
  updated_at: "2026-11-04T10:00:00Z",
});

const simulation = (surcharge: Partial<Simulation> = {}): Simulation => ({
  id: "s1",
  application_id: "c1",
  status: "in_progress",
  questions: [question()],
  answers: [],
  summary: {
    answered: 0,
    total: 1,
    average_score: null,
    best_question_id: null,
    weakest_question_id: null,
    unanswered: ["technical-1"],
  },
  created_at: "2026-11-04T10:00:00Z",
  completed_at: null,
  ...surcharge,
});

const entretien = (surcharge: Partial<Interview> = {}): Interview => ({
  id: "i1",
  application_id: "c1",
  stage: "technical",
  format: "video",
  scheduled_at: "2026-11-10T09:00:00Z",
  location: "Visio",
  interviewers: ["Marie"],
  notes: null,
  outcome: "pending",
  feedback_notes: null,
  follow_up_draft: null,
  created_at: "2026-11-04T10:00:00Z",
  updated_at: "2026-11-04T10:00:00Z",
  ...surcharge,
});

interface Appel {
  url: string;
  methode: string;
  corps?: Record<string, unknown>;
}

interface Reglages {
  preparation?: Preparation | null;
  simulations?: Simulation[];
  entretiens?: Interview[];
  ecriture?: (appel: Appel) => Response | undefined;
}

function simulerApi(r: Reglages = {}) {
  const appels: Appel[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const appel: Appel = {
        url,
        methode: init?.method ?? "GET",
        corps: typeof init?.body === "string" ? JSON.parse(init.body) : undefined,
      };
      appels.push(appel);
      if (appel.methode !== "GET") {
        const reponse = r.ecriture?.(appel);
        if (reponse) return reponse;
        return json({});
      }
      if (url.includes("/preparation")) {
        return r.preparation
          ? json(r.preparation)
          : erreurApi("preparation_not_found", "Aucune préparation.", 404);
      }
      if (url.includes("/simulations")) return json(r.simulations ?? []);
      if (url.includes("/interviews")) return json(r.entretiens ?? []);
      return json({ items: [candidature()], total: 1, limit: 25, offset: 0 });
    }),
  );
  return appels;
}

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <Toaster />
      <InterviewHub />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  recherche = "application=c1";
});
afterEach(() => {
  vi.unstubAllGlobals();
  replace.mockClear();
});

describe("InterviewHub — sélection", () => {
  it("sans candidature choisie, n'affiche pas d'onglets", async () => {
    recherche = "";
    simulerApi();
    afficher();

    expect(await screen.findByLabelText("Candidature")).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Préparation" })).not.toBeInTheDocument();
  });

  it("choisir une candidature met à jour l'URL", async () => {
    recherche = "";
    simulerApi();
    afficher();

    await userEvent.selectOptions(await screen.findByLabelText("Candidature"), "c1");

    expect(replace).toHaveBeenCalledWith("/interview-preparation?application=c1");
  });
});

describe("Préparation", () => {
  it("propose une génération à la demande, sans IA par défaut", async () => {
    const appels = simulerApi({ preparation: null });
    afficher();

    await screen.findByText("Aucune préparation");
    expect(appels.filter((a) => a.methode === "POST")).toHaveLength(0);

    await userEvent.click(screen.getByRole("button", { name: "Préparer l'entretien" }));

    await waitFor(() =>
      expect(appels.find((a) => a.methode === "POST")?.corps).toEqual({ mode: "none" }),
    );
  });

  it("envoie le mode choisi pour l'IA ou le modèle local", async () => {
    const appels = simulerApi({ preparation: null });
    afficher();
    await screen.findByText("Aucune préparation");

    await userEvent.selectOptions(screen.getByLabelText("Assistance"), "local");
    await userEvent.click(screen.getByRole("button", { name: "Préparer l'entretien" }));

    await waitFor(() =>
      expect(appels.find((a) => a.methode === "POST")?.corps).toEqual({ mode: "local" }),
    );
  });

  it("affiche questions, trame à compléter, écarts de compétence et questions recruteur", async () => {
    simulerApi({ preparation: preparation() });
    afficher();

    expect(await screen.findByText(/Décrivez un cas concret/)).toBeInTheDocument();
    expect(screen.getByText("Compétence absente du profil")).toBeInTheDocument();
    expect(screen.getByText(/À compléter : Résultat réel/)).toBeInTheDocument();
    expect(screen.getByText("Comment se passe l'intégration ?")).toBeInTheDocument();
    expect(screen.getByText(/Les passages entre crochets sont à compléter/)).toBeInTheDocument();
  });

  it("dit explicitement quand l'IA demandée est indisponible", async () => {
    const prep = preparation();
    prep.meta.ai = { requested: "ai", status: "unavailable", reason: "Plafond atteint." };
    simulerApi({ preparation: prep });
    afficher();

    const alerte = await screen.findByRole("status");
    expect(within(alerte).getByText("IA indisponible")).toBeInTheDocument();
    expect(alerte).toHaveTextContent("Plafond atteint.");
    expect(alerte).toHaveTextContent("La préparation de base reste complète.");
  });

  it("affiche l'erreur du serveur avec un bouton Réessayer", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) =>
        url.includes("/preparation")
          ? erreurApi("boom", "Serveur indisponible.", 500)
          : json({ items: [candidature()], total: 1, limit: 25, offset: 0 }),
      ),
    );
    afficher();

    expect(await screen.findByText("Serveur indisponible.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Réessayer" })).toBeInTheDocument();
  });
});

describe("Simulation", () => {
  async function ouvrirSimulation(r: Reglages) {
    const appels = simulerApi(r);
    afficher();
    await userEvent.click(await screen.findByRole("tab", { name: "Simulation" }));
    return appels;
  }

  it("démarre une simulation à la demande", async () => {
    const existantes: Simulation[] = [];
    const appels = await ouvrirSimulation({
      simulations: existantes,
      ecriture: (a) => {
        if (!a.url.endsWith("/simulations")) return undefined;
        existantes.push(simulation());
        return json(simulation(), 201);
      },
    });

    await userEvent.click(await screen.findByRole("button", { name: "Démarrer une simulation" }));

    await waitFor(() =>
      expect(appels.find((a) => a.methode === "POST")?.corps).toEqual({ question_count: 6 }),
    );
    expect(await screen.findByText("Simulation en cours")).toBeInTheDocument();
  });

  it("évalue une réponse et affiche le retour, sans IA par défaut", async () => {
    const appels = await ouvrirSimulation({
      simulations: [simulation()],
      ecriture: (a) =>
        a.methode === "PUT"
          ? json({
              question_id: "technical-1",
              text: "Ma réponse",
              answered_at: "2026-11-04T10:05:00Z",
              feedback: {
                score: 72,
                strengths: ["Longueur adaptée."],
                improvements: ["Ajoutez un élément concret."],
                unverified_numbers: [],
                ai_comments: [],
                ai_status: null,
              },
            })
          : undefined,
    });

    await userEvent.click(await screen.findByRole("button", { name: "Ouvrir" }));
    await userEvent.type(await screen.findByLabelText("Votre réponse"), "Ma réponse");
    await userEvent.click(screen.getByRole("button", { name: "Évaluer ma réponse" }));

    await waitFor(() =>
      expect(appels.find((a) => a.methode === "PUT")?.corps).toEqual({
        text: "Ma réponse",
        mode: "none",
      }),
    );
  });

  it("désactive l'évaluation d'une réponse vide", async () => {
    await ouvrirSimulation({ simulations: [simulation()] });

    await userEvent.click(await screen.findByRole("button", { name: "Ouvrir" }));

    expect(await screen.findByRole("button", { name: "Évaluer ma réponse" })).toBeDisabled();
  });

  it("une simulation terminée est en lecture seule et montre son score moyen", async () => {
    await ouvrirSimulation({
      simulations: [
        simulation({
          status: "completed",
          summary: {
            answered: 1,
            total: 1,
            average_score: 80,
            best_question_id: "technical-1",
            weakest_question_id: null,
            unanswered: [],
          },
          answers: [
            {
              question_id: "technical-1",
              text: "Réponse enregistrée",
              answered_at: "2026-11-04T10:05:00Z",
              feedback: {
                score: 80,
                strengths: [],
                improvements: [],
                unverified_numbers: [],
                ai_comments: [],
                ai_status: "unavailable",
              },
            },
          ],
        }),
      ],
    });

    await userEvent.click(await screen.findByRole("button", { name: "Ouvrir" }));

    expect(await screen.findByText("Simulation terminée", { selector: "h2" })).toBeInTheDocument();
    expect(screen.getByLabelText("Votre réponse")).toHaveAttribute("readonly");
    expect(screen.queryByRole("button", { name: "Évaluer ma réponse" })).not.toBeInTheDocument();
    expect(screen.getByText(/Commentaire d'IA indisponible/)).toBeInTheDocument();
    expect(screen.getByText("80/100")).toBeInTheDocument();
  });

  it("supprime une simulation de l'historique", async () => {
    const appels = await ouvrirSimulation({ simulations: [simulation()] });

    await userEvent.click(await screen.findByRole("button", { name: /Supprimer la simulation/ }));

    await waitFor(() =>
      expect(appels.some((a) => a.methode === "DELETE" && a.url.endsWith("/simulations/s1"))).toBe(
        true,
      ),
    );
  });
});

describe("Entretiens", () => {
  async function ouvrirEntretiens(r: Reglages) {
    const appels = simulerApi(r);
    afficher();
    await userEvent.click(await screen.findByRole("tab", { name: "Entretiens" }));
    return appels;
  }

  it("état vide invitant à enregistrer un entretien", async () => {
    await ouvrirEntretiens({});

    expect(await screen.findByText("Aucun entretien enregistré")).toBeInTheDocument();
  });

  it("enregistre un entretien avec une date au format ISO avec fuseau", async () => {
    const appels = await ouvrirEntretiens({ ecriture: () => json(entretien(), 201) });

    await userEvent.click(await screen.findByRole("button", { name: "Ajouter un entretien" }));
    await userEvent.type(screen.getByLabelText("Date et heure"), "2030-01-10T09:30");
    await userEvent.type(screen.getByLabelText("Interlocuteurs"), "Marie, Paul");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    await waitFor(() => expect(appels.some((a) => a.methode === "POST")).toBe(true));
    const corps = appels.find((a) => a.methode === "POST")?.corps as Record<string, unknown>;
    expect(corps.scheduled_at).toMatch(/^2030-01-10T\d{2}:30:00\.000Z$/);
    expect(corps.interviewers).toEqual(["Marie", "Paul"]);
    expect(corps.outcome).toBe("pending");
  });

  it("prépare un brouillon puis planifie la relance à la date proposée", async () => {
    const avecBrouillon = entretien({
      follow_up_draft: {
        subject: "Merci pour notre échange",
        body: "Bonjour Marie,\n\nMerci. [À compléter : un point]",
        suggested_follow_up_at: "2026-11-12T09:00:00Z",
      },
    });
    const appels = await ouvrirEntretiens({
      entretiens: [avecBrouillon],
      ecriture: (a) =>
        a.url.endsWith("/follow-up") ? json({ follow_up_at: "2026-11-12T09:00:00Z" }) : undefined,
    });

    expect(await screen.findByText("Merci pour notre échange")).toBeInTheDocument();
    expect(screen.getByText(/Rien n'est envoyé par l'application/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Planifier la relance/ }));

    await waitFor(() =>
      expect(appels.find((a) => a.url.endsWith("/follow-up"))?.corps).toEqual({}),
    );
  });

  it("sans brouillon, ne propose que d'en préparer un", async () => {
    await ouvrirEntretiens({ entretiens: [entretien()] });

    expect(
      await screen.findByRole("button", { name: "Préparer un brouillon de remerciement" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Planifier la relance/ })).not.toBeInTheDocument();
  });
});
