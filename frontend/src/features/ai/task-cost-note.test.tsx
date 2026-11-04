import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TaskCostNote } from "./task-cost-note";

const json = (corps: unknown, statut = 200) =>
  new Response(JSON.stringify(corps), { status: statut });

function afficher(enabled = true) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <TaskCostNote task="offer_summary" enabled={enabled} />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("TaskCostNote", () => {
  it("affiche le coût maximal et la raison d'un refus avant l'opération", async () => {
    const fetchSimule = vi.fn(async () =>
      json({
        provider: "gemini",
        model: "m",
        paid: true,
        cost: "0.0081",
        currency: "EUR",
        allowed: false,
        reason: "Le plafond de cette tâche (0.01 EUR/jour) serait dépassé.",
      }),
    );
    vi.stubGlobal("fetch", fetchSimule);
    afficher();

    expect(await screen.findByText(/Coût maximal estimé : 0.0081 EUR/)).toBeInTheDocument();
    expect(screen.getByText(/Refusé aujourd'hui : Le plafond de cette tâche/)).toBeInTheDocument();
    const [url, init] = fetchSimule.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain("/api/v1/ai/estimate");
    expect(JSON.parse(init.body as string)).toEqual({ task_type: "offer_summary" });
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
    afficher();

    expect(await screen.findByText(/Gratuit : exécuté en local/)).toBeInTheDocument();
  });

  it("n'interroge pas l'API tant que l'option IA n'est pas choisie", () => {
    const fetchSimule = vi.fn();
    vi.stubGlobal("fetch", fetchSimule);
    afficher(false);

    expect(fetchSimule).not.toHaveBeenCalled();
    expect(screen.queryByRole("note")).toBeNull();
  });

  it("signale une estimation indisponible sans bloquer l'opération", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        json({ error: { code: "ai_not_configured", message: "Aucun fournisseur IA." } }, 409),
      ),
    );
    afficher();

    expect(await screen.findByText(/Coût estimé indisponible/)).toBeInTheDocument();
  });
});
