import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AnalysisResponse, OfferAnalysis } from "@/types/analysis";

import { AnalysisPanel, libelleExperience } from "./analysis-panel";

const json = (corps: unknown, statut = 200) =>
  new Response(JSON.stringify(corps), { status: statut });

const analyse = (extra: Partial<OfferAnalysis> = {}): OfferAnalysis => ({
  version: "a1",
  missions: ["Concevoir des API FastAPI"],
  mandatory_skills: ["Docker"],
  expected_skills: [],
  desired_skills: ["Kubernetes"],
  technologies: ["FastAPI", "Docker"],
  years_experience: 3,
  years_mandatory: true,
  languages: [{ language: "en", level: "courant", mandatory: true, evidence: "Anglais courant" }],
  mobility: { visa: null, relocation_offered: false, travel: null, evidence: [] },
  missing: [{ code: "salary", label: "Salaire non indiqué" }],
  summary: "Nous construisons une plateforme de données.",
  ...extra,
});

const reponse = (a: OfferAnalysis): AnalysisResponse => ({
  analysis_id: "an1",
  computed_at: "2026-11-04T10:00:00Z",
  reused: false,
  analysis: a,
});

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AnalysisPanel offerId="o1" />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("libelleExperience", () => {
  it("distingue une expérience exigée d'une expérience souhaitée, et l'absence", () => {
    expect(libelleExperience(analyse())).toBe("3 ans minimum");
    expect(libelleExperience(analyse({ years_experience: 1, years_mandatory: false }))).toBe(
      "1 an (souhaité)",
    );
    expect(
      libelleExperience(analyse({ years_experience: null, years_mandatory: null })),
    ).toBeNull();
  });
});

describe("AnalysisPanel", () => {
  it("affiche ce que l'annonce dit et ce qu'elle ne dit pas", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(reponse(analyse()))));

    afficher();

    expect(await screen.findByText("Concevoir des API FastAPI")).toBeInTheDocument();
    const obligatoires = screen.getByRole("list", { name: "Compétences obligatoires" });
    expect(within(obligatoires).getByText("Docker")).toBeInTheDocument();
    expect(screen.getByText("3 ans minimum")).toBeInTheDocument();
    expect(screen.getByText(/Anglais — courant \(exigé\)/)).toBeInTheDocument();
    expect(screen.getByText("Salaire non indiqué")).toBeInTheDocument();
    expect(screen.getByText(/Ce qui n'y est pas écrit n'est pas deviné/)).toBeInTheDocument();
  });

  it("n'affiche aucune rubrique vide et la mobilité seulement si elle est mentionnée", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        json(
          reponse(
            analyse({
              missions: [],
              mandatory_skills: [],
              desired_skills: [],
              languages: [],
              years_experience: null,
              years_mandatory: null,
              summary: null,
            }),
          ),
        ),
      ),
    );

    afficher();

    await screen.findByText("Salaire non indiqué");
    expect(screen.queryByText("Missions")).toBeNull();
    expect(screen.queryByText("Langues")).toBeNull();
    expect(screen.queryByText("Mobilité et visa")).toBeNull();
  });

  it("signale le sponsoring de visa et la relocalisation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        json(
          reponse(
            analyse({
              mobility: {
                visa: "no_sponsorship",
                relocation_offered: true,
                travel: "10 %",
                evidence: [],
              },
            }),
          ),
        ),
      ),
    );

    afficher();

    expect(await screen.findByText("Pas de sponsoring de visa")).toBeInTheDocument();
    expect(screen.getByText("Aide à la relocalisation mentionnée")).toBeInTheDocument();
    expect(screen.getByText("Déplacements : 10 %")).toBeInTheDocument();
  });

  it("propose un résumé IA facultatif qui n'envoie que le texte public", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: string, init?: RequestInit) =>
        init?.method === "POST"
          ? json({
              summary: "Poste de développeur Python.",
              key_points: ["API", "SQL"],
              provider: "ollama",
              model: "gemma4:e4b",
              cache_hit: true,
              cost: "0",
            })
          : json(reponse(analyse())),
      ),
    );
    afficher();
    const user = userEvent.setup();

    expect(await screen.findByText(/jamais votre CV/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Résumé par IA" }));

    expect(await screen.findByText("Poste de développeur Python.")).toBeInTheDocument();
    expect(screen.getByText(/déjà résumé \(cache, sans coût\)/)).toBeInTheDocument();
  });

  it("renvoie vers le Centre IA quand l'IA n'est pas utilisable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: string, init?: RequestInit) =>
        init?.method === "POST"
          ? json({ error: { code: "ai_not_configured", message: "Aucun fournisseur IA." } }, 409)
          : json(reponse(analyse())),
      ),
    );
    afficher();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Résumé par IA" }));

    expect(await screen.findByText(/Aucun fournisseur IA/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ouvrir le Centre IA" })).toHaveAttribute(
      "href",
      "/ai-center",
    );
  });

  it("propose de réessayer en cas d'erreur", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          json({ error: { code: "offer_not_found", message: "Offre introuvable." } }, 404),
        ),
    );

    afficher();

    expect(await screen.findByText("Offre introuvable.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Réessayer" })).toBeInTheDocument();
  });
});
