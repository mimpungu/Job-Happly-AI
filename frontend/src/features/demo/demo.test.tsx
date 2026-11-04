import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Toaster } from "@/components/ui/toaster";
import { erreurApi, json } from "@/features/applications/fixtures";

import { DemoBanner } from "./demo-banner";
import { DemoPanel } from "./demo-panel";

const etat = (enabled: boolean, offers = 0, applications = 0) => ({
  enabled,
  offers,
  applications,
  notice: "Données fictives : aucune de ces offres n'existe.",
});

function simulerApi(
  initial: ReturnType<typeof etat> | Response,
  apres?: ReturnType<typeof etat> | Response,
) {
  const appels: { url: string; methode: string }[] = [];
  let courant = initial;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const methode = init?.method ?? "GET";
      appels.push({ url, methode });
      if (methode === "POST" && apres) courant = apres;
      return courant instanceof Response ? courant.clone() : json(courant);
    }),
  );
  return appels;
}

function afficher(ui: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <Toaster />
      {ui}
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("DemoBanner", () => {
  it("n'affiche rien quand la démonstration est inactive", async () => {
    const appels = simulerApi(etat(false));
    afficher(<DemoBanner />);

    await waitFor(() => expect(appels.length).toBeGreaterThan(0));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("signale clairement que les offres sont fictives quand elle est active", async () => {
    simulerApi(etat(true, 8));
    afficher(<DemoBanner />);

    const bandeau = await screen.findByRole("status");
    expect(bandeau).toHaveTextContent("Mode démonstration actif");
    expect(bandeau).toHaveTextContent("fictives");
    expect(screen.getByRole("link", { name: /Désactiver dans les paramètres/ })).toHaveAttribute(
      "href",
      "/settings",
    );
  });

  it("reste silencieux si l'API est injoignable", async () => {
    const appels = simulerApi(erreurApi("boom", "Serveur injoignable.", 503));
    afficher(<DemoBanner />);

    await waitFor(() => expect(appels.length).toBeGreaterThan(0));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});

describe("DemoPanel", () => {
  it("active la démonstration sur demande explicite", async () => {
    const appels = simulerApi(etat(false), etat(true, 8));
    afficher(<DemoPanel />);

    await userEvent.click(
      await screen.findByRole("button", { name: "Activer le mode démonstration" }),
    );

    await waitFor(() =>
      expect(appels.some((a) => a.methode === "POST" && a.url.endsWith("/demo/enable"))).toBe(true),
    );
    expect(await screen.findByText(/8 offre\(s\) fictive\(s\)/)).toBeInTheDocument();
    expect(screen.getByText("Actif")).toBeInTheDocument();
  });

  it("explique que le réel n'est jamais mêlé et propose la désactivation avec suppression", async () => {
    const appels = simulerApi(etat(true, 8, 2), etat(false));
    afficher(<DemoPanel />);

    expect(await screen.findByText(/2 candidature\(s\)/)).toBeInTheDocument();
    expect(screen.getByText(/ne se mélangent jamais/)).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "Désactiver et supprimer les données fictives" }),
    );

    await waitFor(() => expect(appels.some((a) => a.url.endsWith("/demo/disable"))).toBe(true));
    expect(await screen.findByText("Inactif")).toBeInTheDocument();
  });

  it("affiche le refus du serveur quand des données réelles existent", async () => {
    simulerApi(
      etat(false),
      erreurApi(
        "demo_unavailable",
        "Le mode démonstration n'est disponible que sans offre réelle.",
        409,
      ),
    );
    afficher(<DemoPanel />);

    await userEvent.click(
      await screen.findByRole("button", { name: "Activer le mode démonstration" }),
    );

    expect(await screen.findByText(/n'est disponible que sans offre réelle/)).toBeInTheDocument();
  });
});
