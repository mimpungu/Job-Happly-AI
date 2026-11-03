import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Toaster } from "@/components/ui/toaster";
import type { CollectionReport, Company } from "@/types/companies";

import { CompaniesPanel, resumeCollecte } from "./companies-panel";

const json = (corps: unknown, statut = 200) =>
  new Response(JSON.stringify(corps), { status: statut });

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <CompaniesPanel />
      <Toaster />
    </QueryClientProvider>,
  );
}

const entreprise = (extra: Partial<Company> = {}): Company => ({
  id: "c1",
  name: "Acme",
  careers_url: "https://boards.greenhouse.io/acme",
  ats_kind: "greenhouse",
  detection_status: "supported",
  enabled: true,
  last_checked_at: null,
  last_success_at: null,
  last_error: null,
  ...extra,
});

const sortie = (extra: Partial<CollectionReport["sources"][number]> = {}) => ({
  company_id: "c1",
  company_name: "Acme",
  source_key: "greenhouse:acme",
  succeeded: true,
  complete: true,
  fetched: 12,
  created: 5,
  merged: 0,
  changed: 1,
  unchanged: 6,
  rejected: 0,
  expired: 2,
  error_type: null,
  ...extra,
});

afterEach(() => vi.unstubAllGlobals());

describe("resumeCollecte", () => {
  it("compte les nouvelles offres et nomme les sources en échec", () => {
    const rapport: CollectionReport = {
      started_at: "2026-11-03T10:00:00Z",
      finished_at: "2026-11-03T10:00:05Z",
      status: "partial",
      sources: [sortie(), sortie({ source_key: "lever:x", succeeded: false, created: 0 })],
    };

    expect(resumeCollecte(rapport)).toBe(
      "2 sources interrogées · 5 nouvelles offres · 1 source en échec",
    );
  });
});

describe("CompaniesPanel", () => {
  it("invite à chercher une entreprise quand aucune n'est suivie et bloque la collecte", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json([])));

    afficher();

    expect(await screen.findByText(/Aucune entreprise suivie/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Collecter les offres" })).toBeDisabled();
  });

  it("cherche une entreprise par son nom libre puis la suit après confirmation", async () => {
    const appels: { url: string; init?: RequestInit }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        appels.push({ url, init });
        if (url.endsWith("/discover"))
          return json([
            {
              ats_kind: "greenhouse",
              token: "acme",
              careers_url: "https://boards.greenhouse.io/acme",
              board_name: "Acme Corp",
              offer_count: 3,
            },
          ]);
        if (init?.method === "POST") return json(entreprise({ name: "Acme Corp" }), 201);
        return json([]);
      }),
    );
    afficher();
    const user = userEvent.setup();

    await user.type(await screen.findByLabelText("Nom de l'entreprise"), "Acme");
    await user.click(screen.getByRole("button", { name: "Chercher" }));
    const trouves = await screen.findByRole("list", { name: "Sites carrières trouvés" });
    expect(within(trouves).getByText(/Acme Corp · Greenhouse/)).toBeInTheDocument();
    expect(within(trouves).getByText(/3 offres publiées/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Suivre Acme Corp/ }));

    await waitFor(() => {
      const ajout = appels.find(
        (a) => a.url.endsWith("/api/v1/target-companies") && a.init?.method === "POST",
      );
      expect(JSON.parse(String(ajout?.init?.body))).toEqual({
        name: "Acme Corp",
        careers_url: "https://boards.greenhouse.io/acme",
        enabled: true,
      });
    });
  });

  it("explique l'absence de résultat sans prétendre que l'entreprise n'a pas d'offres", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => json(url.endsWith("/discover") ? [] : [])),
    );
    afficher();
    const user = userEvent.setup();

    await user.type(await screen.findByLabelText("Nom de l'entreprise"), "Inconnue");
    await user.click(screen.getByRole("button", { name: "Chercher" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      /Aucun site carrières public[\s\S]*ne veut pas dire/,
    );
  });

  it("affiche le bilan par source, y compris les échecs, après la collecte", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        if (url.endsWith("/collection/run") && init?.method === "POST")
          return json({
            started_at: "2026-11-03T10:00:00Z",
            finished_at: "2026-11-03T10:00:05Z",
            status: "partial",
            sources: [
              sortie(),
              sortie({
                company_name: "Panne",
                source_key: "greenhouse:panne",
                succeeded: false,
                error_type: "SourceUnavailableError",
              }),
            ],
          });
        return json([entreprise()]);
      }),
    );
    afficher();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Collecter les offres" }));

    const sources = await screen.findByRole("list", { name: "Sources interrogées" });
    expect(within(sources).getByText(/12 offres lues · 5 nouvelles/)).toBeInTheDocument();
    expect(within(sources).getByText(/Source indisponible ou refusée/)).toBeInTheDocument();
  });

  it("n'autorise pas l'activation d'une source non reconnue", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          json([entreprise({ enabled: false, detection_status: "pending", ats_kind: null })]),
        ),
    );

    afficher();

    expect(await screen.findByText("Source non reconnue")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Activer Acme" })).toBeDisabled();
  });

  it("envoie les filtres informatique et ville avec la collecte", async () => {
    const corps: unknown[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        if (url.endsWith("/collection/run")) {
          corps.push(JSON.parse(String(init?.body)));
          return json({ started_at: "", finished_at: "", status: "succeeded", sources: [] });
        }
        return json([entreprise()]);
      }),
    );
    afficher();
    const user = userEvent.setup();

    await user.type(await screen.findByLabelText("Ville (facultatif)"), "Paris");
    await user.click(screen.getByRole("button", { name: "Collecter les offres" }));

    await waitFor(() => expect(corps).toEqual([{ it_only: true, city: "Paris" }]));
  });
});
