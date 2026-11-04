import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Toaster } from "@/components/ui/toaster";
import { erreurApi, json } from "@/features/applications/fixtures";
import type {
  AITransfer,
  CategorySummary,
  HealthReport,
  MetricsSnapshot,
  RetentionRule,
} from "@/types/privacy";

import { HealthPanel } from "./health-panel";
import { PrivacyPanel } from "./privacy-panel";

const categories: CategorySummary[] = [
  {
    category: "profile",
    label: "Profil maître (identité, expériences, formations, compétences)",
    rows: 12,
    file_bytes: 0,
    tables: {},
  },
  {
    category: "documents",
    label: "CV et lettres générés (versions et fichiers PDF)",
    rows: 4,
    file_bytes: 2_500_000,
    tables: {},
  },
];
const regles: RetentionRule[] = [
  {
    table: "ai_cache_entries",
    category: "ai_activity",
    days: 30,
    description: "Réponses IA mises en cache",
    automatic: true,
  },
  {
    table: "applications",
    category: "applications",
    days: null,
    description: "Candidatures et historique",
    automatic: false,
  },
];
const transferts: AITransfer[] = [
  {
    task_type: "cv_rewrite",
    purpose: "Reformuler les réalisations d'un CV",
    data_sent: "Texte des réalisations",
    never_sent: "Identité, CV complet",
    personal_data: true,
    optional: true,
  },
];

interface Appel {
  url: string;
  methode: string;
  corps?: Record<string, unknown>;
}

function simulerApi(
  options: {
    policy?: string;
    erase?: () => Response;
    sante?: HealthReport | Response;
    mesures?: MetricsSnapshot;
  } = {},
) {
  const appels: Appel[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      appels.push({
        url,
        methode: init?.method ?? "GET",
        corps: typeof init?.body === "string" ? JSON.parse(init.body) : undefined,
      });
      if (url.endsWith("/privacy/erase"))
        return (
          options.erase?.() ??
          json({
            scope: "x",
            total_rows: 5,
            rows_deleted: {},
            files_deleted: 0,
            files_failed: 0,
            notes: [],
          })
        );
      if (url.endsWith("/privacy/summary")) return json(categories);
      if (url.endsWith("/privacy/retention")) return json(regles);
      if (url.endsWith("/privacy/ai-transfers")) return json(transferts);
      if (url.endsWith("/privacy/settings"))
        return json({
          personal_data_policy: options.policy ?? "allowed",
          confirmation_word: "SUPPRIMER",
        });
      if (url.endsWith("/health/details"))
        return options.sante instanceof Response
          ? options.sante
          : json(options.sante ?? { status: "ok", components: [] });
      if (url.endsWith("/health/metrics"))
        return json(
          options.mesures ?? {
            uptime_seconds: 3600,
            requests: 0,
            server_errors: 0,
            rate_limited: 0,
            routes: {},
          },
        );
      return json({});
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

describe("PrivacyPanel", () => {
  it("montre ce qui est stocké par catégorie, avec la taille des fichiers", async () => {
    simulerApi();
    afficher(<PrivacyPanel />);

    expect(await screen.findByText(/12 ligne\(s\)/)).toBeInTheDocument();
    expect(screen.getByText(/4 ligne\(s\) · fichiers 2\.4 Mo/)).toBeInTheDocument();
  });

  it("propose l'export comme un téléchargement local", async () => {
    simulerApi();
    afficher(<PrivacyPanel />);

    const lien = await screen.findByRole("link", { name: /Exporter mes données/ });

    expect(lien).toHaveAttribute("href", expect.stringContaining("/api/v1/privacy/export"));
    expect(lien).toHaveAttribute("download");
  });

  it("n'active la suppression qu'après la saisie exacte du mot de confirmation", async () => {
    const appels = simulerApi();
    afficher(<PrivacyPanel />);

    await userEvent.click(await screen.findByRole("button", { name: "Tout supprimer" }));
    const dialogue = await screen.findByRole("dialog", { name: "Suppression définitive" });
    const bouton = within(dialogue).getByRole("button", { name: "Supprimer définitivement" });
    expect(bouton).toBeDisabled();

    await userEvent.type(within(dialogue).getByLabelText(/Saisissez SUPPRIMER/), "supprim");
    expect(bouton).toBeDisabled();
    await userEvent.clear(within(dialogue).getByLabelText(/Saisissez SUPPRIMER/));
    await userEvent.type(within(dialogue).getByLabelText(/Saisissez SUPPRIMER/), "SUPPRIMER");
    expect(bouton).toBeEnabled();
    await userEvent.click(bouton);

    await waitFor(() =>
      expect(appels.find((a) => a.url.endsWith("/privacy/erase"))?.corps).toEqual({
        scope: "all",
        confirmation: "SUPPRIMER",
      }),
    );
  });

  it("supprime une seule catégorie", async () => {
    const appels = simulerApi();
    afficher(<PrivacyPanel />);

    const boutons = await screen.findAllByRole("button", { name: /^Supprimer /u });
    await userEvent.click(boutons[0] as HTMLElement);
    const dialogue = await screen.findByRole("dialog");
    await userEvent.type(within(dialogue).getByLabelText(/Saisissez SUPPRIMER/), "SUPPRIMER");
    await userEvent.click(
      within(dialogue).getByRole("button", { name: "Supprimer définitivement" }),
    );

    await waitFor(() =>
      expect(appels.find((a) => a.url.endsWith("/privacy/erase"))?.corps?.scope).toBe("profile"),
    );
  });

  it("affiche l'erreur du serveur lors d'une suppression refusée", async () => {
    simulerApi({
      erase: () => erreurApi("deletion_blocked", "Supprimez d'abord les candidatures.", 409),
    });
    afficher(<PrivacyPanel />);

    await userEvent.click(await screen.findByRole("button", { name: "Tout supprimer" }));
    const dialogue = await screen.findByRole("dialog");
    await userEvent.type(within(dialogue).getByLabelText(/Saisissez SUPPRIMER/), "SUPPRIMER");
    await userEvent.click(
      within(dialogue).getByRole("button", { name: "Supprimer définitivement" }),
    );

    expect(await screen.findByText("Supprimez d'abord les candidatures.")).toBeInTheDocument();
  });

  it("enregistre la politique d'envoi des données personnelles à l'IA", async () => {
    const appels = simulerApi({ policy: "allowed" });
    afficher(<PrivacyPanel />);

    await userEvent.selectOptions(
      await screen.findByLabelText(/Envoi de mes données personnelles/),
      "never",
    );

    await waitFor(() =>
      expect(appels.find((a) => a.methode === "PUT")?.corps).toEqual({
        personal_data_policy: "never",
      }),
    );
  });

  it("documente ce qui part vers l'IA et la conservation de chaque donnée", async () => {
    simulerApi();
    afficher(<PrivacyPanel />);

    expect(await screen.findByText("Reformuler les réalisations d'un CV")).toBeInTheDocument();
    expect(screen.getByText("Données personnelles")).toBeInTheDocument();
    expect(screen.getByText(/Identité, CV complet/)).toBeInTheDocument();
    expect(screen.getByText(/30 jours · purge automatique/)).toBeInTheDocument();
    expect(screen.getByText(/Jusqu'à suppression par vous/)).toBeInTheDocument();
  });
});

describe("HealthPanel", () => {
  it("affiche chaque composant avec son état, un composant facultatif absent n'est pas une panne", async () => {
    simulerApi({
      sante: {
        status: "degraded",
        components: [
          { name: "database", status: "ok", detail: null, data: {} },
          {
            name: "ai",
            status: "not_configured",
            detail: "Aucun fournisseur IA configuré.",
            data: {},
          },
          { name: "tasks", status: "degraded", detail: "2 tâche(s) en retard", data: {} },
        ],
      },
    });
    afficher(<HealthPanel />);

    expect(await screen.findByText("Base de données")).toBeInTheDocument();
    expect(screen.getByText("Non configuré")).toBeInTheDocument();
    expect(screen.getByText("2 tâche(s) en retard")).toBeInTheDocument();
    expect(screen.getAllByText("Dégradé").length).toBeGreaterThanOrEqual(2);
  });

  it("présente les durées par route, les plus lentes en premier", async () => {
    simulerApi({
      mesures: {
        uptime_seconds: 90,
        requests: 12,
        server_errors: 1,
        rate_limited: 0,
        routes: {
          "GET /rapide": { count: 5, errors: 0, avg_ms: 3, p50_ms: 3, p95_ms: 5 },
          "POST /lente": { count: 2, errors: 1, avg_ms: 800, p50_ms: 700, p95_ms: 950 },
        },
      },
    });
    afficher(<HealthPanel />);

    expect(await screen.findByText(/12 requête\(s\), 1 erreur\(s\) serveur/)).toBeInTheDocument();
    const lignes = await screen.findAllByRole("row");
    expect(within(lignes[1] as HTMLElement).getByText("POST /lente")).toBeInTheDocument();
  });

  it("signale clairement l'impossibilité de lire la santé", async () => {
    simulerApi({ sante: erreurApi("boom", "Serveur injoignable.", 503) });
    afficher(<HealthPanel />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Serveur injoignable.");
  });
});
