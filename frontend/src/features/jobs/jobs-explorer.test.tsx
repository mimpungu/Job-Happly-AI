import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
let recherche = "";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  usePathname: () => "/jobs",
  useSearchParams: () => new URLSearchParams(recherche),
}));

import { Toaster } from "@/components/ui/toaster";
import type { OfferPage, OfferSummary } from "@/types/jobs";

import { JobsExplorer } from "./jobs-explorer";

const offre = (surcharge: Partial<OfferSummary> = {}): OfferSummary => ({
  id: "o1",
  title: "Data Analyst",
  company_name: "Exemple SA",
  location: "Paris, France",
  country_code: "FR",
  employment_type: "permanent",
  remote_type: null,
  salary_min: null,
  salary_max: null,
  salary_currency: null,
  published_at: "2026-11-01T10:00:00Z",
  status: "active",
  state: null,
  source_keys: ["france_travail"],
  match_score: null,
  match_reliability: null,
  ...surcharge,
});

const page = (items: OfferSummary[], surcharge: Partial<OfferPage> = {}): OfferPage => ({
  items,
  total: items.length,
  page: 1,
  page_size: 25,
  page_count: 1,
  ...surcharge,
});

function json(corps: unknown, statut = 200) {
  return new Response(JSON.stringify(corps), { status: statut });
}

/** Route minimale : l'API locale est simulée, jamais le réseau réel. */
function simulerApi(
  offres: () => Response,
  etat: () => Response = () => new Response(null, { status: 204 }),
) {
  const appels: { url: string; methode: string; corps?: string }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      appels.push({ url, methode: init?.method ?? "GET", corps: init?.body as string | undefined });
      if (url.includes("/saved-searches")) return json([]);
      if (url.includes("/search-runs")) return json([]);
      if (url.includes("/state")) return etat();
      return offres();
    }),
  );
  return appels;
}

function afficher(props: { savedOnly?: boolean } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <JobsExplorer {...props} />
      <Toaster />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  push.mockClear();
  recherche = "";
});
afterEach(() => vi.unstubAllGlobals());

describe("JobsExplorer", () => {
  it("affiche un chargement puis les offres avec leurs sources", async () => {
    simulerApi(() => json(page([offre()])));
    afficher();

    expect(screen.getByRole("status", { name: "Chargement des offres" })).toBeInTheDocument();
    const tableau = await screen.findByRole("table", { name: "Résultats de la recherche" });

    expect(within(tableau).getByRole("link", { name: "Data Analyst" })).toHaveAttribute(
      "href",
      "/jobs/o1",
    );
    expect(within(tableau).getByText("france_travail")).toBeInTheDocument();
    expect(within(tableau).getByText("CDI")).toBeInTheDocument();
    // Le salaire et le télétravail inconnus sont dits inconnus, jamais affichés comme 0.
    expect(within(tableau).getAllByText("Non renseigné").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("1 offre")).toBeInTheDocument();
  });

  it("explique un résultat vide", async () => {
    simulerApi(() => json(page([])));
    afficher();

    expect(await screen.findByText("Aucune offre ne correspond")).toBeInTheDocument();
  });

  it("affiche l'erreur de l'API et permet de réessayer", async () => {
    let echec = true;
    simulerApi(() =>
      echec
        ? json({ error: { code: "internal_error", message: "Erreur interne." } }, 500)
        : json(page([offre()])),
    );
    afficher();

    expect(await screen.findByText("Impossible de charger les offres")).toBeInTheDocument();
    expect(screen.getByText("Erreur interne.")).toBeInTheDocument();

    echec = false;
    await userEvent.click(screen.getByRole("button", { name: "Réessayer" }));

    expect(await screen.findByRole("table")).toBeInTheDocument();
  });

  it("signale un serveur injoignable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fetch failed")));
    afficher();

    expect(await screen.findByText(/Impossible de joindre le serveur local/)).toBeInTheDocument();
  });

  it("sauvegarde une offre via l'API puis recharge la liste", async () => {
    const appels = simulerApi(() => json(page([offre()])));
    afficher();

    await userEvent.click(
      await screen.findByRole("button", { name: "Sauvegarder l'offre : Data Analyst" }),
    );

    await waitFor(() => {
      const ecriture = appels.find((a) => a.methode === "PUT");
      expect(ecriture?.url).toContain("/api/v1/offers/o1/state");
      expect(JSON.parse(ecriture?.corps ?? "{}")).toEqual({ state: "saved" });
    });
    expect(await screen.findByText("Offre sauvegardée.")).toBeInTheDocument();
  });

  it("propose de retirer une offre déjà sauvegardée", async () => {
    const appels = simulerApi(() => json(page([offre({ state: "saved" })])));
    afficher();

    await userEvent.click(
      await screen.findByRole("button", { name: "Retirer des offres sauvegardées : Data Analyst" }),
    );

    await waitFor(() => {
      const ecriture = appels.find((a) => a.methode === "PUT");
      expect(JSON.parse(ecriture?.corps ?? "{}")).toEqual({ state: null });
    });
  });

  it("met les critères dans l'URL au clic sur Rechercher", async () => {
    simulerApi(() => json(page([])));
    afficher();
    await screen.findByText("Aucune offre ne correspond");

    await userEvent.type(screen.getByLabelText("Intitulé, mot-clé ou entreprise"), "python");
    await userEvent.type(screen.getByLabelText("Ville"), "Lyon");
    await userEvent.click(screen.getByRole("button", { name: "Rechercher" }));

    expect(push).toHaveBeenCalledWith("/jobs?text=python&city=Lyon");
  });

  it("refuse un salaire sans devise", async () => {
    simulerApi(() => json(page([])));
    afficher();
    await screen.findByText("Aucune offre ne correspond");

    await userEvent.type(screen.getByLabelText("Salaire minimum"), "40000");
    await userEvent.clear(screen.getByLabelText("Devise"));

    expect(screen.getByRole("alert")).toHaveTextContent("La devise est obligatoire");
    expect(screen.getByRole("button", { name: "Rechercher" })).toBeDisabled();
  });

  it("pagine via l'URL", async () => {
    simulerApi(() => json(page([offre()], { total: 60, page_count: 3 })));
    afficher();

    await userEvent.click(await screen.findByRole("button", { name: /Suivant/ }));

    expect(push).toHaveBeenCalledWith("/jobs?page=2");
  });

  it("relit la recherche depuis l'URL et la transmet à l'API", async () => {
    recherche = "text=python&sort=title_asc&page=2";
    const appels = simulerApi(() => json(page([offre()], { page: 2, page_count: 2 })));
    afficher();

    await screen.findByRole("table");

    const liste = appels.find((a) => a.url.includes("/api/v1/offers?"));
    expect(liste?.url).toContain("text=python");
    expect(liste?.url).toContain("sort=title_asc");
    expect(liste?.url).toContain("page=2");
    expect(screen.getByLabelText("Intitulé, mot-clé ou entreprise")).toHaveValue("python");
  });

  it("la page des offres sauvegardées impose l'état et masque le formulaire", async () => {
    const appels = simulerApi(() => json(page([])));
    afficher({ savedOnly: true });

    expect(await screen.findByText("Aucune offre sauvegardée")).toBeInTheDocument();
    expect(screen.queryByRole("form", { name: "Recherche d'offres" })).not.toBeInTheDocument();
    expect(appels.find((a) => a.url.includes("/api/v1/offers?"))?.url).toContain("state=saved");
  });

  it("affiche la compatibilité de chaque offre, ou « Non évalué » quand elle n'existe pas", async () => {
    simulerApi(() =>
      json(
        page([
          offre({
            id: "o1",
            title: "Data Analyst",
            match_score: "72.00",
            match_reliability: "medium",
          }),
          offre({ id: "o2", title: "Comptable" }),
        ]),
      ),
    );
    afficher();

    const tableau = await screen.findByRole("table");

    expect(within(tableau).getByRole("meter", { name: "Compatibilité" })).toHaveAttribute(
      "aria-valuenow",
      "72",
    );
    expect(within(tableau).getByText("Fiabilité moyenne")).toBeInTheDocument();
    expect(within(tableau).getByText("Non évalué")).toBeInTheDocument();
  });

  it("met la compatibilité minimale dans l'URL", async () => {
    simulerApi(() => json(page([])));
    afficher();
    await screen.findByText("Aucune offre ne correspond");

    await userEvent.selectOptions(screen.getByLabelText("Compatibilité minimale"), "70");
    await userEvent.click(screen.getByRole("button", { name: "Rechercher" }));

    expect(push).toHaveBeenCalledWith("/jobs?min_score=70");
  });

  it("renvoie vers l'Espace CV quand le tri ou le filtre par score est impossible", async () => {
    recherche = "sort=score_desc";
    simulerApi(() =>
      json(
        {
          error: {
            code: "scoring_unavailable",
            message: "Le tri et le filtre par score exigent un profil validé.",
          },
        },
        409,
      ),
    );
    afficher();

    expect(await screen.findByText("Compatibilité indisponible")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Valider mon profil" })).toHaveAttribute(
      "href",
      "/cv-studio",
    );
    expect(screen.queryByRole("button", { name: "Réessayer" })).toBeNull();
  });

  it("calcule les scores à la demande et annonce le résultat", async () => {
    const appels: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        appels.push(`${init?.method ?? "GET"} ${url}`);
        if (url.includes("/matching/recompute"))
          return json({
            computed: 4,
            not_computable: 0,
            profile_version: 1,
            weights_version: "m1-x",
          });
        if (url.includes("/saved-searches") || url.includes("/search-runs")) return json([]);
        return json(page([offre()]));
      }),
    );
    afficher();
    await screen.findByRole("table");

    await userEvent.click(screen.getByRole("button", { name: "Calculer les scores" }));

    expect(await screen.findByText("4 offres évaluées.")).toBeInTheDocument();
    expect(appels.some((a) => a.startsWith("POST") && a.includes("/matching/recompute"))).toBe(
      true,
    );
  });

  it("signale que la liste affichée est en cours de mise à jour pendant un rechargement", async () => {
    let liberer: (r: Response) => void = () => undefined;
    let appel = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.includes("/saved-searches") || url.includes("/search-runs"))
          return Promise.resolve(json([]));
        appel += 1;
        if (appel === 1) return Promise.resolve(json(page([offre()], { page_count: 2 })));
        return new Promise<Response>((resolve) => {
          liberer = resolve;
        });
      }),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    // Fonction : chaque appel crée un élément neuf (un élément identique ferait sauter le rendu).
    const ui = () => (
      <QueryClientProvider client={client}>
        <JobsExplorer />
      </QueryClientProvider>
    );
    const { rerender } = render(ui());
    await screen.findByRole("table");
    expect(screen.getByRole("region", { name: "Résultats" })).not.toHaveAttribute("aria-busy");

    recherche = "page=2";
    rerender(ui());

    // L'ancienne page reste visible mais elle est marquée « en cours de mise à jour ».
    await waitFor(() =>
      expect(screen.getByRole("region", { name: "Résultats" })).toHaveAttribute(
        "aria-busy",
        "true",
      ),
    );
    expect(screen.getByRole("table")).toBeInTheDocument();

    liberer(json(page([offre({ title: "Autre offre" })], { page: 2, page_count: 2 })));

    expect(await screen.findByText("Autre offre")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Résultats" })).not.toHaveAttribute("aria-busy");
  });
});
