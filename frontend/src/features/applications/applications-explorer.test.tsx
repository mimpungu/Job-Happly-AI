import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
let recherche = "";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  usePathname: () => "/applications",
  useSearchParams: () => new URLSearchParams(recherche),
}));

import { ApplicationsExplorer } from "./applications-explorer";
import { candidature, erreurApi, json, stats } from "./fixtures";

import type { KanbanView } from "@/types/applications";
import { APPLICATION_STATUSES } from "@/types/application-status";

const kanban = (surcharge: Partial<Record<string, { count: number; items: unknown[] }>> = {}) =>
  ({
    columns: APPLICATION_STATUSES.map((status) => {
      const s = surcharge[status] ?? { count: 0, items: [] };
      return { status, count: s.count, items: s.items, has_more: s.count > s.items.length };
    }),
  }) as KanbanView;

function simulerApi(liste: () => Response, vueKanban: () => Response = () => json(kanban())) {
  const appels: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      appels.push(url);
      if (url.includes("/stats")) return json(stats());
      if (url.includes("/kanban")) return vueKanban();
      return liste();
    }),
  );
  return appels;
}

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ApplicationsExplorer />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  recherche = "";
});
afterEach(() => {
  vi.unstubAllGlobals();
  push.mockClear();
});

const page = (items = [candidature()], total = items.length) =>
  json({ items, total, limit: 25, offset: 0 });

describe("ApplicationsExplorer — tableau", () => {
  it("affiche les candidatures avec leur offre, leur statut et un lien vers la fiche", async () => {
    simulerApi(() =>
      page([
        candidature({ status: "sent", applied_at: "2026-11-03T12:00:00Z" }),
        candidature({
          id: "c2",
          status: "to_apply",
          follow_up_at: "2020-01-01T12:00:00Z",
          offer: { ...candidature().offer!, title: "Data Engineer", company_name: null },
        }),
      ]),
    );
    afficher();

    const tableau = await screen.findByRole("table", { name: "Candidatures" });
    expect(within(tableau).getByRole("link", { name: "Développeur Python" })).toHaveAttribute(
      "href",
      "/applications/c1",
    );
    expect(within(tableau).getByText("Envoyée")).toBeInTheDocument();
    expect(within(tableau).getByText("Entreprise inconnue")).toBeInTheDocument();
    expect(within(tableau).getByText("Échue")).toBeInTheDocument(); // relance de 2020
    expect(screen.getByText("2 candidatures")).toBeInTheDocument();
  });

  it("montre les statistiques et n'affiche pas de taux sans candidature envoyée", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) =>
        url.includes("/stats")
          ? json(stats({ sent_applications: 0, response_rate: null }))
          : url.includes("/kanban")
            ? json(kanban())
            : page(),
      ),
    );
    afficher();

    expect(await screen.findByText("Aucune candidature envoyée")).toBeInTheDocument();
    const zone = within(screen.getByLabelText("Statistiques de suivi"));
    expect(zone.getByText("—")).toBeInTheDocument();
    expect(zone.queryByText("0 %")).not.toBeInTheDocument();
  });

  it("propose de chercher des offres quand rien n'est suivi", async () => {
    simulerApi(() => page([], 0));
    afficher();

    expect(await screen.findByText("Aucune candidature")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Chercher des offres" })).toHaveAttribute(
      "href",
      "/jobs",
    );
  });

  it("distingue « rien de suivi » de « rien ne correspond aux filtres »", async () => {
    recherche = "status=sent";
    simulerApi(() => page([], 0));
    afficher();

    expect(await screen.findByText("Aucune candidature ne correspond")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Réinitialiser les filtres" }));
    expect(push).toHaveBeenCalledWith("/applications");
  });

  it("applique les filtres à l'URL, à la première page", async () => {
    recherche = "page=3";
    simulerApi(() => page());
    afficher();

    await userEvent.selectOptions(await screen.findByLabelText("Statut"), "interview");
    await userEvent.type(screen.getByLabelText("Entreprise"), "Acme");
    await userEvent.click(screen.getByRole("button", { name: "Filtrer" }));

    expect(push).toHaveBeenCalledWith("/applications?status=interview&company=Acme");
  });

  it("interroge l'API avec les filtres de l'URL", async () => {
    recherche = "status=sent&relance=due&page=2";
    const appels = simulerApi(() => page());
    afficher();

    await screen.findByRole("table");
    const requete = appels.find((u) => u.includes("/applications?"));
    expect(requete).toContain("status=sent");
    expect(requete).toContain("follow_up_due=true");
    expect(requete).toContain("offset=25");
  });

  it("annonce une erreur de chargement et permet de réessayer", async () => {
    let echec = true;
    simulerApi(() => (echec ? erreurApi("internal_error", "Erreur interne.", 500) : page()));
    afficher();

    expect(await screen.findByText("Impossible de charger les candidatures")).toBeInTheDocument();
    echec = false;
    await userEvent.click(screen.getByRole("button", { name: "Réessayer" }));
    expect(await screen.findByRole("table", { name: "Candidatures" })).toBeInTheDocument();
  });
});

describe("ApplicationsExplorer — Kanban", () => {
  beforeEach(() => {
    recherche = "vue=kanban";
  });

  it("affiche toutes les colonnes avec leur total réel et un accès au reste", async () => {
    simulerApi(
      () => page(),
      () =>
        json(
          kanban({
            to_apply: { count: 23, items: [candidature(), candidature({ id: "c2" })] },
            sent: { count: 1, items: [candidature({ id: "c3", status: "sent" })] },
          }),
        ),
    );
    afficher();

    const colonne = await screen.findByRole("region", { name: "À postuler : 23" });
    expect(within(colonne).getAllByRole("link", { name: "Développeur Python" })).toHaveLength(2);
    expect(within(colonne).getByRole("link", { name: /21 autres/ })).toHaveAttribute(
      "href",
      "/applications?status=to_apply",
    );
    expect(screen.getByRole("region", { name: "Envoyée : 1" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Abandonnée : 0" })).toHaveTextContent(
      "Aucune candidature",
    );
    expect(screen.getAllByRole("region", { name: /: \d+$/ })).toHaveLength(12);
  });

  it("propose de chercher des offres quand tout est vide", async () => {
    simulerApi(() => page([], 0));
    afficher();
    expect(await screen.findByText("Aucune candidature")).toBeInTheDocument();
  });

  it("change de vue via l'URL", async () => {
    recherche = "";
    simulerApi(() => page());
    afficher();

    await userEvent.click(await screen.findByRole("tab", { name: "Kanban" }));
    expect(push).toHaveBeenCalledWith("/applications?vue=kanban");
  });
});
