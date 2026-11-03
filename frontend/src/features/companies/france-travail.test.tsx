import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Toaster } from "@/components/ui/toaster";
import type { FranceTravailResult } from "@/types/companies";

import { FranceTravailPanel, resumeRecherche } from "./france-travail-panel";

const json = (corps: unknown, statut = 200) =>
  new Response(JSON.stringify(corps), { status: statut });

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <FranceTravailPanel />
      <Toaster />
    </QueryClientProvider>,
  );
}

const resultat = (extra: Partial<FranceTravailResult> = {}): FranceTravailResult => ({
  succeeded: true,
  complete: true,
  pages: 1,
  fetched: 12,
  created: 5,
  merged: 0,
  changed: 0,
  unchanged: 7,
  rejected: 0,
  error_type: null,
  ...extra,
});

afterEach(() => vi.unstubAllGlobals());

describe("resumeRecherche", () => {
  it("nomme l'échec au lieu d'annoncer zéro offre", () => {
    expect(
      resumeRecherche(resultat({ succeeded: false, error_type: "AuthenticationFailedError" })),
    ).toMatch(/refusé les identifiants/);
    expect(resumeRecherche(resultat())).toBe("12 offres lues · 5 nouvelles");
  });
});

describe("FranceTravailPanel", () => {
  it("explique comment configurer la source quand elle ne l'est pas", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ configured: false })));

    afficher();

    expect(await screen.findByText("Non configuré")).toBeInTheDocument();
    expect(screen.getByText(/a retiré l'API/)).toBeInTheDocument();
    expect(screen.getByText(/HAPPLY_FRANCE_TRAVAIL_CLIENT_ID/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Rechercher sur France Travail/ })).toBeNull();
  });

  it("envoie la recherche par entreprise, ville et département", async () => {
    const corps: unknown[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        if (url.endsWith("/status")) return json({ configured: true });
        corps.push(JSON.parse(String(init?.body)));
        return json(resultat());
      }),
    );
    afficher();
    const user = userEvent.setup();

    await user.type(await screen.findByLabelText("Entreprise"), "BNP Paribas");
    await user.type(screen.getByLabelText("Ville"), "Paris");
    await user.type(screen.getByLabelText("Département"), "75");
    await user.click(screen.getByRole("button", { name: "Rechercher sur France Travail" }));

    await waitFor(() =>
      expect(corps).toEqual([
        { title: null, company: "BNP Paribas", keywords: [], city: "Paris", department: "75" },
      ]),
    );
    expect(await screen.findByRole("status")).toHaveTextContent("12 offres lues · 5 nouvelles");
  });

  it("refuse un département invalide et exige un critère", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ configured: true })));
    afficher();
    const user = userEvent.setup();
    const bouton = await screen.findByRole("button", { name: "Rechercher sur France Travail" });
    expect(bouton).toBeDisabled();

    await user.type(screen.getByLabelText("Entreprise"), "BNP");
    await user.type(screen.getByLabelText("Département"), "7X");

    expect(screen.getByText("Code de département invalide.")).toBeInTheDocument();
    expect(bouton).toBeDisabled();
  });
});
