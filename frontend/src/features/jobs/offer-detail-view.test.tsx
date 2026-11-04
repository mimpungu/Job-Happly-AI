import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();

// La fiche propose « Suivre cette candidature », qui navigue vers la fiche créée.
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

import { Toaster } from "@/components/ui/toaster";
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
      <Toaster />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  push.mockClear();
});

describe("safeHttpUrl", () => {
  it("n'accepte que http et https", () => {
    expect(safeHttpUrl("https://a.test/x")).toBe("https://a.test/x");
    expect(safeHttpUrl("javascript:alert(1)")).toBeNull();
    expect(safeHttpUrl("data:text/html,x")).toBeNull();
    expect(safeHttpUrl("pas une url")).toBeNull();
    expect(safeHttpUrl(null)).toBeNull();
  });
});

describe("OfferDetailView : mobilité internationale", () => {
  it("dit ce que l'annonce précise, sans deviner ce qu'elle ne précise pas", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(
            JSON.stringify(
              detail({ visa_sponsorship: "not_offered", work_authorization_required: true }),
            ),
          ),
        ),
    );
    afficher();

    const liste = await screen.findByRole("list", { name: "Mobilité internationale" });

    expect(liste).toHaveTextContent("Sponsoring de visa : non proposé par l'annonce");
    expect(liste).toHaveTextContent("Droit de travailler exigé");
  });

  it("affiche « non précisé » pour une annonce muette", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(detail()))));
    afficher();

    const liste = await screen.findByRole("list", { name: "Mobilité internationale" });

    expect(liste).toHaveTextContent("Sponsoring de visa : non précisé");
    expect(liste).toHaveTextContent("Droit de travailler : non précisé");
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

  it("crée la candidature de l'offre puis ouvre sa fiche", async () => {
    const appels: { url: string; methode: string; corps?: string }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        appels.push({ url, methode: init?.method ?? "GET", corps: init?.body as string });
        if (url.endsWith("/api/v1/applications"))
          return new Response(JSON.stringify({ id: "c1" }), { status: 201 });
        if (url.includes("/match") || url.includes("/analysis"))
          return new Response(JSON.stringify({ error: { code: "x", message: "indisponible" } }), {
            status: 503,
          });
        return new Response(JSON.stringify(detail()));
      }),
    );
    afficher();

    await userEvent.click(await screen.findByRole("button", { name: "Suivre cette candidature" }));
    // Un clic ne crée rien : une confirmation explicite est demandée d'abord.
    expect(appels.some((a) => a.methode === "POST")).toBe(false);
    await userEvent.click(await screen.findByRole("button", { name: "Ajouter au suivi" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/applications/c1"));
    const creation = appels.find((a) => a.methode === "POST" && a.url.endsWith("/applications"));
    expect(JSON.parse(creation?.corps ?? "{}")).toEqual({
      offer_id: "o1",
      initial_status: "to_apply",
    });
  });

  it("n'ajoute rien quand on annule la confirmation", async () => {
    const appels: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        appels.push(init?.method ?? "GET");
        if (url.includes("/match") || url.includes("/analysis"))
          return new Response(JSON.stringify({ error: { code: "x", message: "indisponible" } }), {
            status: 503,
          });
        return new Response(JSON.stringify(detail()));
      }),
    );
    afficher();

    await userEvent.click(await screen.findByRole("button", { name: "Suivre cette candidature" }));
    await userEvent.click(await screen.findByRole("button", { name: "Annuler" }));

    expect(appels).not.toContain("POST");
    expect(push).not.toHaveBeenCalled();
  });

  it("signale une offre déjà suivie au lieu de créer un doublon", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        if (init?.method === "POST")
          return new Response(
            JSON.stringify({ error: { code: "duplicate_application", message: "déjà" } }),
            { status: 409 },
          );
        if (url.includes("/match") || url.includes("/analysis"))
          return new Response(JSON.stringify({ error: { code: "x", message: "indisponible" } }), {
            status: 503,
          });
        return new Response(JSON.stringify(detail()));
      }),
    );
    afficher();

    await userEvent.click(await screen.findByRole("button", { name: "Suivre cette candidature" }));
    await userEvent.click(await screen.findByRole("button", { name: "Ajouter au suivi" }));

    expect(await screen.findByText(/déjà suivie/)).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });
});
