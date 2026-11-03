import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Toaster } from "@/components/ui/toaster";
import type { AISettings, AIUsage } from "@/types/ai";

import { AICenter, montantValide } from "./ai-center";

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
  budget_defined: false,
  api_consent: false,
  api_consent_at: null,
  providers: [],
  paid_calls_possible: false,
  ...extra,
});

const consommation = (extra: Partial<AIUsage> = {}): AIUsage => ({
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

describe("AICenter", () => {
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
    simuler(reglages(), consommation(), ecritures);
    afficher();
    const user = userEvent.setup();

    await user.selectOptions(await screen.findByLabelText("Mode"), "quality");
    await user.selectOptions(screen.getByLabelText("Où exécuter l'IA"), "local_only");

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
