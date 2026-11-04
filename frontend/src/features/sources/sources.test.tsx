import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { DataSource, SourceSearchResult } from "@/types/sources";

import { DataSourcesPanel } from "./data-sources-panel";
import { QueriedSources } from "./queried-sources";

const source = (surcharge: Partial<DataSource> = {}): DataSource => ({
  key: "greenhouse:acme",
  name: "Acme (Greenhouse)",
  kind: "public_ats",
  countries: [],
  enabled: true,
  requires_configuration: false,
  configured: true,
  status: "ok",
  last_checked_at: "2026-11-04T10:00:00Z",
  last_success_at: "2026-11-04T10:00:00Z",
  last_error: null,
  offer_count: 12,
  ...surcharge,
});

afterEach(() => vi.unstubAllGlobals());

describe("DataSourcesPanel", () => {
  it("signale une source non configurée et une source en erreur", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify([
              source(),
              source({
                key: "france_travail",
                name: "France Travail (API officielle)",
                countries: ["FR"],
                requires_configuration: true,
                configured: false,
                status: "not_configured",
                last_checked_at: null,
                last_success_at: null,
                offer_count: 0,
              }),
              source({
                key: "lever:panne",
                name: "Panne (Lever)",
                status: "error",
                last_error: "unavailable: SourceUnavailableError",
              }),
            ]),
          ),
      ),
    );
    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <DataSourcesPanel />
      </QueryClientProvider>,
    );

    const ft = (await screen.findByText("France Travail (API officielle)")).closest("li")!;
    expect(within(ft).getByText("Non configurée")).toBeInTheDocument();
    expect(within(ft).getByText(/Identifiants requis/)).toBeInTheDocument();
    const panne = screen.getByText("Panne (Lever)").closest("li")!;
    expect(within(panne).getByText("En erreur")).toBeInTheDocument();
    expect(within(panne).getByText(/SourceUnavailableError/)).toBeInTheDocument();
    expect(screen.getByText("Opérationnelle")).toBeInTheDocument();
  });
});

describe("QueriedSources", () => {
  const base: SourceSearchResult = {
    queried: true,
    status: "partial",
    sources: [
      {
        source_key: "greenhouse:a",
        source_name: "A (Greenhouse)",
        status: "ok",
        complete: true,
        fetched: 5,
        created: 2,
        merged: 0,
        changed: 0,
        unchanged: 3,
        rejected: 0,
        error_type: null,
      },
      {
        source_key: "lever:b",
        source_name: "B (Lever)",
        status: "failed",
        complete: false,
        fetched: 0,
        created: 0,
        merged: 0,
        changed: 0,
        unchanged: 0,
        rejected: 0,
        error_type: "AccessDeniedError",
      },
    ],
    results: { items: [], total: 0, page: 1, page_size: 25, page_count: 1 },
  };

  it("nomme chaque échec et signale le résultat partiel", () => {
    render(<QueriedSources result={base} />);

    expect(screen.getByText(/résultats partiels/)).toBeInTheDocument();
    expect(screen.getByText(/2 nouvelles/)).toBeInTheDocument();
    expect(screen.getByText(/accès refusé/)).toBeInTheDocument();
  });

  it("affiche la couverture géographique sans rien affirmer de plus", () => {
    render(
      <QueriedSources
        result={{
          ...base,
          coverage: {
            requested: ["FR", "CA"],
            declared: ["FR"],
            undeclared: ["CA"],
            sources_without_declared_countries: ["greenhouse:a"],
          },
        }}
      />,
    );

    expect(screen.getByText(/Pays couverts par une source interrogée : FR/)).toBeInTheDocument();
    expect(
      screen.getByText(/Aucune source interrogée ne déclare couvrir : CA/),
    ).toBeInTheDocument();
    expect(screen.getByText(/couverture n'est pas déclarée/)).toBeInTheDocument();
  });

  it("n'affiche aucune couverture quand aucun pays n'est demandé", () => {
    render(
      <QueriedSources
        result={{
          ...base,
          coverage: {
            requested: [],
            declared: [],
            undeclared: [],
            sources_without_declared_countries: [],
          },
        }}
      />,
    );

    expect(screen.queryByText(/Pays couverts/)).toBeNull();
  });

  it("dit clairement qu'aucune source n'a été interrogée", () => {
    render(<QueriedSources result={{ ...base, queried: false, status: null, sources: [] }} />);

    expect(screen.getByRole("status")).toHaveTextContent("Aucune source activée");
  });
});
