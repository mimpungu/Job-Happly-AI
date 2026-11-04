import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Toaster } from "@/components/ui/toaster";
import type { AISettings } from "@/types/ai";

import {
  AlertesBudget,
  EstimationCout,
  PlafondsFournisseurs,
  PlafondsParTache,
} from "./budget-extras";

const json = (corps: unknown, statut = 200) =>
  new Response(JSON.stringify(corps), { status: statut });

function avec(noeud: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      {noeud}
      <Toaster />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("AlertesBudget", () => {
  it("n'affiche rien sous le premier seuil", () => {
    const { container } = avec(<AlertesBudget alertes={[]} devise="EUR" />);

    expect(container.querySelector("ul")).toBeNull();
  });

  it("explique le blocage quand le plafond est atteint", () => {
    avec(
      <AlertesBudget
        devise="EUR"
        alertes={[
          { period: "daily", threshold: 100, percent: "100.0", spent: "1.00", limit: "1.00" },
          { period: "monthly", threshold: 50, percent: "55.0", spent: "5.50", limit: "10.00" },
        ]}
      />,
    );

    expect(screen.getByText("Seuil 100 %")).toBeInTheDocument();
    expect(screen.getByText(/appels payants sont bloqués/)).toBeInTheDocument();
    expect(screen.getByText(/mensuel utilisé à 55.0 %/)).toBeInTheDocument();
  });
});

describe("PlafondsFournisseurs", () => {
  const reglages = (extra: Partial<AISettings> = {}) =>
    ({
      currency: "EUR",
      provider_daily_caps: { gemini: "0.50" },
      providers: [
        { name: "gemini", kind: "api", models: ["m"], uses_data_for_training: false },
        { name: "ollama", kind: "local", models: ["l"], uses_data_for_training: false },
      ],
      ...extra,
    }) as AISettings;

  it("ne propose un plafond que pour les fournisseurs payants et envoie la valeur saisie", async () => {
    const fetchSimule = vi.fn(async () => json(reglages()));
    vi.stubGlobal("fetch", fetchSimule);
    avec(<PlafondsFournisseurs reglages={reglages()} />);

    expect(screen.queryByRole("form", { name: "Plafond de ollama" })).toBeNull();
    const champ = screen.getByLabelText(/gemini — plafond journalier/);
    expect(champ).toHaveValue("0.50");
    await userEvent.clear(champ);
    await userEvent.type(champ, "0.25");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    await waitFor(() => expect(fetchSimule).toHaveBeenCalled());
    const [url, init] = fetchSimule.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain("/api/v1/ai/provider-caps/gemini");
    expect(JSON.parse(init.body as string)).toEqual({ daily: "0.25" });
  });

  it("refuse un montant invalide", async () => {
    avec(<PlafondsFournisseurs reglages={reglages()} />);

    const champ = screen.getByLabelText(/gemini — plafond journalier/);
    await userEvent.clear(champ);
    await userEvent.type(champ, "-3");

    expect(screen.getByText(/Montant positif/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Enregistrer" })).toBeDisabled();
  });
});

describe("EstimationCout", () => {
  it("affiche le coût maximal et la raison d'un refus", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        json({
          provider: "gemini",
          model: "m",
          paid: true,
          cost: "0.008151",
          currency: "EUR",
          allowed: false,
          reason: "Aucun plafond défini.",
        }),
      ),
    );
    avec(<EstimationCout />);

    await userEvent.click(screen.getByRole("button", { name: "Estimer" }));

    expect(await screen.findByText(/Coût maximal : 0.008151 EUR/)).toBeInTheDocument();
    expect(screen.getByText(/Refusé aujourd'hui : Aucun plafond défini/)).toBeInTheDocument();
  });

  it("annonce un traitement gratuit en local", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        json({
          provider: "ollama",
          model: "l",
          paid: false,
          cost: "0",
          currency: "EUR",
          allowed: true,
          reason: null,
        }),
      ),
    );
    avec(<EstimationCout />);

    await userEvent.click(screen.getByRole("button", { name: "Estimer" }));

    expect(await screen.findByText(/Gratuit : exécuté en local/)).toBeInTheDocument();
  });
});

describe("PlafondsParTache", () => {
  it("liste les tâches de l'application et envoie le plafond de la tâche", async () => {
    const reglages = {
      currency: "EUR",
      task_daily_caps: { cv_rewrite: "0.05" },
      tasks: [
        { task_type: "cv_rewrite", label: "Reformulation des réalisations du CV" },
        { task_type: "offer_summary", label: "Résumé d'une offre par l'IA" },
      ],
    } as unknown as AISettings;
    const fetchSimule = vi.fn(async () => json(reglages));
    vi.stubGlobal("fetch", fetchSimule);
    avec(<PlafondsParTache reglages={reglages} />);

    const champ = screen.getByLabelText(/Reformulation des réalisations du CV — plafond/);
    expect(champ).toHaveValue("0.05");
    expect(screen.getByLabelText(/Résumé d'une offre par l'IA — plafond/)).toHaveValue("");
    await userEvent.clear(champ);
    await userEvent.type(champ, "0.10");
    await userEvent.click(
      within(screen.getByRole("form", { name: /Plafond de la tâche Reformulation/ })).getByRole(
        "button",
        { name: "Enregistrer" },
      ),
    );

    await waitFor(() => expect(fetchSimule).toHaveBeenCalled());
    const [url, init] = fetchSimule.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain("/api/v1/ai/task-caps/cv_rewrite");
    expect(JSON.parse(init.body as string)).toEqual({ daily: "0.10" });
  });
});
