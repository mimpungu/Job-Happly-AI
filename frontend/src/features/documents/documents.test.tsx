import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Toaster } from "@/components/ui/toaster";
import { erreurApi, json } from "@/features/applications/fixtures";
import type { CoverLetter, ResumeDocument } from "@/types/documents";

import { CvLibrary } from "./cv-library";
import { LettersPage } from "./letters-page";

const offres = {
  items: [
    { id: "o1", title: "Développeur Python", company_name: "Acme" },
    { id: "o2", title: "Data Engineer", company_name: null },
  ],
  total: 2,
  page: 1,
  page_size: 25,
  page_count: 1,
};

const cv = (surcharge: Partial<ResumeDocument> = {}): ResumeDocument => ({
  id: "d1",
  title: "CV - Développeur Python",
  language: "fr",
  offer_id: "o1",
  created_at: "2026-11-04T10:00:00Z",
  versions: [
    {
      id: "v1",
      version: 1,
      created_at: "2026-11-04T10:00:00Z",
      size_bytes: 52_000,
      ats_report: {
        score: 94,
        passed: true,
        checks: [],
        page_count: 1,
        keywords_found: ["Python"],
        keywords_missing: ["Kubernetes"],
      },
      generation: {
        origin: "generated",
        ai_rewrite: {
          requested: "ai",
          status: "unavailable",
          rewritten: 0,
          rejected: 0,
          provider: null,
          reason: "Plafond atteint.",
        },
      },
    },
  ],
  ...surcharge,
});

const lettre = (): CoverLetter => ({
  id: "l1",
  title: "Lettre - Développeur Python (Acme)",
  language: "fr",
  offer_id: "o1",
  created_at: "2026-11-04T10:00:00Z",
  versions: [
    {
      id: "lv1",
      version: 1,
      created_at: "2026-11-04T10:00:00Z",
      size_bytes: 40_000,
      audit: {
        score: 82,
        passed: true,
        word_count: 280,
        length_status: "optimal",
        cv_coherent: true,
        page_count: 1,
        spelling_issues: [],
        generic_phrases_detected: [],
        issues: ["Aucune demande d'entretien."],
      },
    },
  ],
  content: {
    subject: "Candidature au poste de Développeur Python",
    salutation: "Madame, Monsieur,",
    introduction: "Je vous écris au sujet du poste.",
    background_highlight: "Chez OpenCorp, j'ai migré 12 services.",
    added_value: "Je maîtrise Python.",
    closing_and_call_to_action: "Je reste disponible.",
    complimentary_close: "Cordialement,",
    signature: "Camille Dubois",
    word_count: 280,
  },
});

interface Appel {
  url: string;
  methode: string;
  corps?: Record<string, unknown>;
}

function simulerApi(
  options: {
    cvs?: ResumeDocument[] | Response;
    lettres?: CoverLetter[] | Response;
    ecriture?: (a: Appel) => Response;
  } = {},
) {
  const appels: Appel[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const appel: Appel = {
        url,
        methode: init?.method ?? "GET",
        corps: typeof init?.body === "string" ? JSON.parse(init.body) : undefined,
      };
      appels.push(appel);
      if (appel.methode === "POST") return options.ecriture?.(appel) ?? json(cv(), 201);
      if (url.includes("/offers")) return json(offres);
      if (url.includes("/cover-letters"))
        return options.lettres instanceof Response ? options.lettres : json(options.lettres ?? []);
      return options.cvs instanceof Response ? options.cvs : json(options.cvs ?? []);
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

describe("CvLibrary", () => {
  it("état vide : invite à valider le profil puis à générer", async () => {
    simulerApi({ cvs: [] });
    afficher(<CvLibrary />);

    expect(await screen.findByText("Aucun CV généré")).toBeInTheDocument();
  });

  it("liste les CV avec score ATS, mots-clés absents et liens de téléchargement", async () => {
    simulerApi({ cvs: [cv()] });
    afficher(<CvLibrary />);

    expect(await screen.findByText("ATS 94/100")).toBeInTheDocument();
    expect(screen.getByText(/Kubernetes/)).toBeInTheDocument();
    const pdf = screen.getByRole("link", { name: /PDF — CV - Développeur Python, version 1/ });
    expect(pdf).toHaveAttribute("href", expect.stringContaining("/resumes/d1/versions/1/pdf"));
    expect(screen.getByRole("link", { name: /LaTeX/ })).toHaveAttribute("download");
  });

  it("dit explicitement quand la reformulation IA était indisponible", async () => {
    simulerApi({ cvs: [cv()] });
    afficher(<CvLibrary />);

    const alerte = await screen.findByRole("status");
    expect(alerte).toHaveTextContent("Reformulation indisponible");
    expect(alerte).toHaveTextContent("Plafond atteint.");
    expect(alerte).toHaveTextContent("Vos réalisations d'origine ont été conservées.");
  });

  it("génère un CV général sans IA par défaut", async () => {
    const appels = simulerApi({ cvs: [] });
    afficher(<CvLibrary />);
    await screen.findByText("Aucun CV généré");

    await userEvent.click(screen.getByRole("button", { name: "Générer le CV" }));

    await waitFor(() => {
      const post = appels.find((a) => a.methode === "POST");
      expect(post?.url).toContain("/resumes/generate");
      expect(post?.corps).toEqual({
        style: "classic",
        length_target: "auto",
        language: "fr",
        rewrite_mode: "none",
      });
    });
  });

  it("cible une offre et choisit la reformulation locale", async () => {
    const appels = simulerApi({ cvs: [] });
    afficher(<CvLibrary />);
    await screen.findByText("Aucun CV généré");

    await screen.findByRole("option", { name: /Développeur Python — Acme/ });
    await userEvent.selectOptions(screen.getByLabelText(/Offre ciblée/), "o1");
    await userEvent.selectOptions(screen.getByLabelText("Reformulation des réalisations"), "local");
    await userEvent.click(screen.getByRole("button", { name: "Générer le CV" }));

    await waitFor(() => {
      const corps = appels.find((a) => a.methode === "POST")?.corps;
      expect(corps).toMatchObject({ offer_id: "o1", rewrite_mode: "local" });
    });
  });

  it("affiche l'erreur du serveur quand il n'y a pas de profil validé", async () => {
    simulerApi({
      cvs: [],
      ecriture: () => erreurApi("no_validated_profile", "Aucun profil validé.", 409),
    });
    afficher(<CvLibrary />);
    await screen.findByText("Aucun CV généré");

    await userEvent.click(screen.getByRole("button", { name: "Générer le CV" }));

    expect(await screen.findByText("Aucun profil validé.")).toBeInTheDocument();
  });

  it("erreur de chargement avec bouton Réessayer", async () => {
    simulerApi({ cvs: erreurApi("boom", "Serveur indisponible.", 500) });
    afficher(<CvLibrary />);

    expect(await screen.findByText("Serveur indisponible.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Réessayer" })).toBeInTheDocument();
  });
});

describe("LettersPage", () => {
  it("la génération exige une offre", async () => {
    simulerApi({ lettres: [] });
    afficher(<LettersPage />);

    expect(await screen.findByRole("button", { name: "Générer la lettre" })).toBeDisabled();
    expect(await screen.findByText("Aucune lettre")).toBeInTheDocument();
  });

  it("génère une lettre pour l'offre choisie avec destinataire et motivation", async () => {
    const appels = simulerApi({ lettres: [], ecriture: () => json(lettre(), 201) });
    afficher(<LettersPage />);

    await screen.findByRole("option", { name: /Développeur Python — Acme/ });
    await userEvent.selectOptions(screen.getByLabelText(/Offre ciblée/), "o1");
    await userEvent.type(screen.getByLabelText(/Destinataire/), "  Marie Martin ");
    await userEvent.type(screen.getByLabelText(/Votre motivation/), "J'aime ce produit.");
    await userEvent.click(screen.getByRole("button", { name: "Générer la lettre" }));

    await waitFor(() =>
      expect(appels.find((a) => a.methode === "POST")?.corps).toEqual({
        offer_id: "o1",
        language: "fr",
        recipient_name: "Marie Martin",
        motivation: "J'aime ce produit.",
      }),
    );
  });

  it("montre l'audit, les points à vérifier, la relecture et les téléchargements", async () => {
    simulerApi({ lettres: [lettre()] });
    afficher(<LettersPage />);

    expect(await screen.findByText("Qualité 82/100")).toBeInTheDocument();
    expect(screen.getByText("Cohérente avec le CV")).toBeInTheDocument();
    expect(screen.getByText("Points à vérifier (1)")).toBeInTheDocument();
    expect(screen.getByText("Aucune demande d'entretien.")).toBeInTheDocument();
    // le texte n'est relisible qu'à la génération : une lettre déjà enregistrée n'en affiche pas
    expect(screen.queryByText("Relire la lettre avant envoi")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /PDF — Lettre/ })).toHaveAttribute(
      "href",
      expect.stringContaining("/cover-letters/l1/versions/1/pdf"),
    );
  });

  it("affiche le texte à relire juste après la génération", async () => {
    simulerApi({ lettres: [], ecriture: () => json(lettre(), 201) });
    afficher(<LettersPage />);

    await screen.findByRole("option", { name: /Développeur Python — Acme/ });
    await userEvent.selectOptions(screen.getByLabelText(/Offre ciblée/), "o1");
    await userEvent.click(screen.getByRole("button", { name: "Générer la lettre" }));

    const relecture = await screen.findByRole("heading", { name: "Relire la lettre avant envoi" });
    const zone = relecture.closest("section") as HTMLElement;
    expect(within(zone).getByText(/Chez OpenCorp/)).toBeInTheDocument();
    expect(within(zone).getByText(/l'application n'envoie jamais rien/)).toBeInTheDocument();
  });

  it("signale une incohérence avec le CV comme un danger", async () => {
    const l = lettre();
    if (l.versions[0]?.audit) l.versions[0].audit.cv_coherent = false;
    simulerApi({ lettres: [l] });
    afficher(<LettersPage />);

    expect(await screen.findByText("Incohérence avec le CV")).toBeInTheDocument();
  });

  it("erreur de chargement avec bouton Réessayer", async () => {
    simulerApi({ lettres: erreurApi("boom", "Serveur indisponible.", 500) });
    afficher(<LettersPage />);

    expect(await screen.findByText("Serveur indisponible.")).toBeInTheDocument();
  });
});
