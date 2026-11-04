import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Toaster } from "@/components/ui/toaster";
import type { AISettings, AIUsage } from "@/types/ai";

import { AICenter, choixIA, choixIndisponible, montantValide } from "./ai-center";

const json = (corps: unknown, statut = 200) =>
  new Response(JSON.stringify(corps), { status: statut });

const reglages = (extra: Partial<AISettings> = {}): AISettings => ({
  mode: "economy",
  backend_preference: "hybrid",
  per_operation_level1: "0.02",
  per_operation_level2: "0.30",
  currency: "EUR",
  daily_budget: null,
  monthly_budget: null,
  alert_thresholds: [50, 80, 100],
  provider_daily_caps: {},
  budget_defined: false,
  api_consent: false,
  api_consent_at: null,
  providers: [],
  paid_calls_possible: false,
  ...extra,
});

const consommation = (extra: Partial<AIUsage> = {}): AIUsage => ({
  alerts: [],
  currency: "EUR",
  spent_today: "0",
  spent_month: "0",
  daily_budget: null,
  monthly_budget: null,
  percent_today: null,
  percent_month: null,
  by_provider_month: {},
  recent: [],
  ...extra,
});

function simuler(
  etat: AISettings,
  usage: AIUsage,
  ecritures: { url: string; corps: unknown }[] = [],
) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === "PUT") {
        ecritures.push({ url, corps: JSON.parse(String(init.body)) });
        return json(etat);
      }
      return json(url.endsWith("/usage") ? usage : etat);
    }),
  );
}

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AICenter />
      <Toaster />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("montantValide", () => {
  it("n'accepte que des montants positifs à deux décimales au plus", () => {
    expect(montantValide("1")).toBe(true);
    expect(montantValide("10.5")).toBe(true);
    expect(montantValide("0")).toBe(false);
    expect(montantValide("-1")).toBe(false);
    expect(montantValide("1.234")).toBe(false);
    expect(montantValide("abc")).toBe(false);
  });
});

const OLLAMA = {
  name: "ollama",
  kind: "local" as const,
  models: ["gemma4:e4b"],
  uses_data_for_training: false,
};
const GEMINI = {
  name: "gemini",
  kind: "api" as const,
  models: ["gemini-3.1-flash-lite"],
  uses_data_for_training: true,
};

describe("choixIA", () => {
  it("propose Ollama, Gemini et l'automatique quand les deux sont configurés", () => {
    const options = choixIA([OLLAMA, GEMINI]);

    expect(options.map((o) => o.value)).toEqual(["hybrid", "local_only", "api_only"]);
    expect(options.every((o) => !o.disabled)).toBe(true);
    expect(options[0]?.label).toBe("Automatique : Ollama d'abord, Gemini en renfort");
    expect(options[2]?.label).toMatch(/palier gratuit, textes publics seulement/);
  });

  it("désactive ce qui n'est pas configuré en disant ce qui manque", () => {
    const options = choixIA([OLLAMA]);

    expect(options.find((o) => o.value === "api_only")).toMatchObject({
      disabled: true,
      label: "Gemini — non configuré (clé absente)",
    });
    expect(options.find((o) => o.value === "hybrid")?.disabled).toBe(true);
    expect(options.find((o) => o.value === "local_only")?.disabled).toBe(false);
  });

  it("signale un choix enregistré devenu indisponible", () => {
    const sansGemini = reglages({ backend_preference: "api_only", providers: [OLLAMA] });
    const ok = reglages({ backend_preference: "local_only", providers: [OLLAMA] });

    expect(choixIndisponible(sansGemini)).toBe(true);
    expect(choixIndisponible(ok)).toBe(false);
  });
});

describe("AICenter", () => {
  it("change d'IA depuis la liste et refuse un fournisseur non configuré", async () => {
    const ecritures: { url: string; corps: unknown }[] = [];
    simuler(reglages({ providers: [OLLAMA] }), consommation(), ecritures);
    afficher();
    const user = userEvent.setup();

    const liste = await screen.findByLabelText("IA utilisée");
    expect(
      screen.getByRole("option", { name: "Gemini — non configuré (clé absente)" }),
    ).toBeDisabled();
    await user.selectOptions(liste, "local_only");

    await waitFor(() =>
      expect(ecritures.map((e) => e.corps)).toEqual([{ backend_preference: "local_only" }]),
    );
  });

  it("avertit sur le palier gratuit et lance le test de bout en bout", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        if (url.endsWith("/ai/test") && init?.method === "POST")
          return json({
            provider: "gemini",
            model: "gemini-3.1-flash-lite",
            cache_hit: true,
            cost: "0",
            input_tokens: 0,
            output_tokens: 0,
            summary: "Poste Python à Paris.",
            skills: ["Python", "SQL"],
            crossed_thresholds: [],
          });
        if (url.endsWith("/usage")) return json(consommation());
        return json(
          reglages({
            providers: [
              {
                name: "gemini",
                kind: "api",
                models: ["gemini-3.1-flash-lite"],
                uses_data_for_training: true,
              },
            ],
          }),
        );
      }),
    );
    afficher();
    const user = userEvent.setup();

    expect(await screen.findByText("Palier gratuit détecté.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /niveau 1/ }));

    const resultat = await screen.findByText(/servi par le cache/);
    expect(resultat).toHaveTextContent("gemini · gemini-3.1-flash-lite");
    expect(screen.getByText("Poste Python à Paris.")).toBeInTheDocument();
  });

  it("affiche l'erreur claire du serveur quand le test est refusé", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        if (init?.method === "POST")
          return json(
            { error: { code: "ai_budget_not_defined", message: "Aucun plafond défini." } },
            409,
          );
        return json(url.endsWith("/usage") ? consommation() : reglages());
      }),
    );
    afficher();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: /niveau 2/ }));

    expect(await screen.findByText("Aucun plafond défini.")).toBeInTheDocument();
  });

  it("dit clairement qu'aucun appel payant n'est possible et que l'app marche sans IA", async () => {
    simuler(reglages(), consommation());

    afficher();

    expect(await screen.findByText("Aucun appel payant possible")).toBeInTheDocument();
    expect(screen.getByText(/fonctionne entièrement sans IA/)).toBeInTheDocument();
    expect(screen.getByText("Envoi à l'API non accepté")).toBeInTheDocument();
    expect(screen.getByText(/Aucun appel IA enregistré/)).toBeInTheDocument();
  });

  it("enregistre les plafonds et refuse un journalier supérieur au mensuel", async () => {
    const ecritures: { url: string; corps: unknown }[] = [];
    simuler(reglages(), consommation(), ecritures);
    afficher();
    const user = userEvent.setup();
    const formulaire = await screen.findByRole("form", { name: "Plafonds de dépense" });

    await user.type(within(formulaire).getByLabelText(/journalier/), "20");
    await user.type(within(formulaire).getByLabelText(/mensuel/), "10");
    expect(screen.getByRole("alert")).toHaveTextContent("ne peut pas dépasser");
    expect(within(formulaire).getByRole("button", { name: /Enregistrer/ })).toBeDisabled();

    await user.clear(within(formulaire).getByLabelText(/journalier/));
    await user.type(within(formulaire).getByLabelText(/journalier/), "1");
    await user.click(within(formulaire).getByRole("button", { name: /Enregistrer/ }));

    await waitFor(() =>
      expect(ecritures).toEqual([
        {
          url: expect.stringContaining("/ai/budget"),
          corps: { daily: "1", monthly: "10", currency: "EUR" },
        },
      ]),
    );
  });

  it("change le mode et la préférence local/API/hybride", async () => {
    const ecritures: { url: string; corps: unknown }[] = [];
    simuler(reglages({ providers: [OLLAMA] }), consommation(), ecritures);
    afficher();
    const user = userEvent.setup();

    await user.selectOptions(await screen.findByLabelText("Mode"), "quality");
    await user.selectOptions(screen.getByLabelText("IA utilisée"), "local_only");

    await waitFor(() =>
      expect(ecritures.map((e) => e.corps)).toEqual([
        { mode: "quality" },
        { backend_preference: "local_only" },
      ]),
    );
  });

  it("demande un accord explicite avant tout envoi à une API payante", async () => {
    const ecritures: { url: string; corps: unknown }[] = [];
    simuler(reglages(), consommation(), ecritures);
    afficher();
    const user = userEvent.setup();

    expect(await screen.findByText(/CV complet n'est jamais envoyé/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "J'accepte l'envoi de ces données" }));

    await waitFor(() => expect(ecritures[0]?.corps).toEqual({ accepted: true }));
  });

  it("affiche la consommation avec une jauge accessible et le journal, refus compris", async () => {
    simuler(
      reglages({ budget_defined: true, daily_budget: "1.00", monthly_budget: "10.00" }),
      consommation({
        spent_today: "0.5",
        percent_today: "50.0",
        daily_budget: "1.00",
        monthly_budget: "10.00",
        recent: [
          {
            at: "2026-11-04T10:00:00Z",
            provider: "api-test",
            model: "petit",
            task_type: "offer_summary",
            level: 1,
            outcome: "blocked_budget",
            cache_hit: false,
            input_tokens: 0,
            output_tokens: 0,
            cost: "0",
            currency: "EUR",
          },
        ],
      }),
    );

    afficher();

    const jauge = await screen.findByRole("meter", { name: "Aujourd'hui" });
    expect(jauge).toHaveAttribute("aria-valuenow", "50");
    expect(screen.getByText("Bloqué (plafond)")).toBeInTheDocument();
  });
});
