import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { OfferDetail } from "@/types/jobs";

import { OfferDetailView, safeHttpUrl } from "./offer-detail-view";

const detail = (surcharge: Partial<OfferDetail> = {}): OfferDetail => ({
  summary: {
    id: "o1",
    title: "Data Analyst",
    company_name: "Exemple SA",
    location: "Paris",
    country_code: "FR",
    employment_type: "permanent",
    remote_type: "hybrid",
    salary_min: null,
    salary_max: null,
    salary_currency: null,
    published_at: "2026-11-01T10:00:00Z",
    status: "active",
    state: null,
    source_keys: ["a"],
    match_score: null,
    match_reliability: null,
  },
  description: "Ligne 1\n<img src=x onerror=alert(1)> ligne 2",
  application_url: "https://exemple.test/apply",
  language: "fr",
  expires_at: null,
  first_seen_at: "2026-11-01T10:00:00Z",
  last_seen_at: "2026-11-02T10:00:00Z",
  sources: [
    {
      source_key: "a",
      source_name: "Source A",
      source_url: "javascript:alert(1)",
      last_seen_at: "2026-11-02T10:00:00Z",
      still_listed: false,
    },
  ],
  ...surcharge,
});

function afficher(id = "o1") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <OfferDetailView id={id} />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("safeHttpUrl", () => {
  it("n'accepte que http et https", () => {
    expect(safeHttpUrl("https://a.test/x")).toBe("https://a.test/x");
    expect(safeHttpUrl("javascript:alert(1)")).toBeNull();
    expect(safeHttpUrl("data:text/html,x")).toBeNull();
    expect(safeHttpUrl("pas une url")).toBeNull();
    expect(safeHttpUrl(null)).toBeNull();
  });
});

describe("OfferDetailView", () => {
  it("affiche la description comme du texte, jamais comme du HTML", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(detail()))));
    const { container } = afficher();

    expect(await screen.findByRole("heading", { name: "Data Analyst" })).toBeInTheDocument();
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByText(/<img src=x onerror=alert\(1\)>/)).toBeInTheDocument();
  });

  it("n'expose pas un lien de source dangereux et signale une source qui ne liste plus l'offre", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(detail()))));
    afficher();

    await screen.findByText("Source A");

    expect(screen.queryByRole("link", { name: "Source A" })).toBeNull();
    expect(screen.getByText(/n'est plus listée par cette source/)).toBeInTheDocument();
    const annonce = screen.getByRole("link", { name: /annonce d'origine/ });
    expect(annonce).toHaveAttribute("href", "https://exemple.test/apply");
    expect(annonce).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("indique une offre introuvable sans proposer de réessayer", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ error: { code: "offer_not_found", message: "Offre introuvable." } }),
          {
            status: 404,
          },
        ),
      ),
    );
    afficher();

    expect(await screen.findByText("Offre introuvable", { selector: "h2" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Réessayer" })).toBeNull();
  });
});
