import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Toaster } from "@/components/ui/toaster";

import { ApplicationDetailView } from "./application-detail-view";
import { detail, dossier, erreurApi, json } from "./fixtures";

import type { ApplicationDetail } from "@/types/applications";

interface Appel {
  url: string;
  methode: string;
  corps?: Record<string, unknown>;
}

function simulerApi(
  fiche: () => Response | ApplicationDetail,
  options: {
    dossier?: unknown;
    ecriture?: (appel: Appel) => Response | undefined;
    cvs?: unknown[];
    lettres?: unknown[];
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
      if (appel.methode !== "GET") {
        const reponse = options.ecriture?.(appel);
        if (reponse) return reponse;
        return json(detail());
      }
      if (url.includes("/dossier")) return json(options.dossier ?? dossier());
      if (url.includes("/open-url"))
        return json({ application_url: "https://careers.example.test/apply" });
      if (url.includes("/resumes")) return json(options.cvs ?? []);
      if (url.includes("/cover-letters")) return json(options.lettres ?? []);
      const corps = fiche();
      return corps instanceof Response ? corps : json(corps);
    }),
  );
  return appels;
}

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ApplicationDetailView id="c1" />
      <Toaster />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("ApplicationDetailView", () => {
  it("affiche l'offre, le statut, l'historique et rappelle que l'utilisateur candidate lui-même", async () => {
    simulerApi(() => detail());
    afficher();

    expect(
      await screen.findByRole("heading", { level: 1, name: "Développeur Python" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Acme · Paris/)).toBeInTheDocument();
    expect(screen.getByText(/vous candidatez vous-même/)).toBeInTheDocument();
    const historique = screen.getByRole("list", { name: "Historique de la candidature" });
    expect(within(historique).getByText("À postuler")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Voir l'offre" })).toHaveAttribute("href", "/jobs/o1");
  });

  it("n'ouvre l'annonce que dans un nouvel onglet isolé, avec le lien vérifié par le serveur", async () => {
    const ouvrir = vi.spyOn(window, "open").mockReturnValue(null);
    simulerApi(() => detail());
    afficher();

    await userEvent.click(await screen.findByRole("button", { name: "Ouvrir l'annonce" }));

    await waitFor(() =>
      expect(ouvrir).toHaveBeenCalledWith(
        "https://careers.example.test/apply",
        "_blank",
        "noopener,noreferrer",
      ),
    );
    ouvrir.mockRestore();
  });

  it("signale un lien d'annonce refusé par le serveur sans rien ouvrir", async () => {
    const ouvrir = vi.spyOn(window, "open").mockReturnValue(null);
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) =>
        url.includes("/open-url")
          ? erreurApi("application_url_unavailable", "URL de candidature invalide.", 422)
          : url.includes("/dossier")
            ? json(dossier())
            : url.includes("/resumes") || url.includes("/cover-letters")
              ? json([])
              : json(detail()),
      ),
    );
    afficher();

    await userEvent.click(await screen.findByRole("button", { name: "Ouvrir l'annonce" }));

    expect(await screen.findByText("URL de candidature invalide.")).toBeInTheDocument();
    expect(ouvrir).not.toHaveBeenCalled();
    ouvrir.mockRestore();
  });

  it("propose uniquement les statuts atteignables et jamais « Envoyée »", async () => {
    simulerApi(() => detail());
    afficher();

    const select = await screen.findByLabelText("Changer le statut");
    const choix = within(select)
      .getAllByRole("option")
      .map((o) => o.textContent);
    expect(choix).toEqual([
      "Choisir un statut",
      "Documents à préparer",
      "Prête à envoyer",
      "Abandonnée",
    ]);
  });

  it("change le statut choisi", async () => {
    const appels = simulerApi(() => detail());
    afficher();

    await userEvent.selectOptions(await screen.findByLabelText("Changer le statut"), "abandoned");
    await userEvent.click(screen.getByRole("button", { name: "Appliquer" }));

    await waitFor(() =>
      expect(appels.find((a) => a.methode === "PATCH")?.corps).toEqual({
        target_status: "abandoned",
      }),
    );
  });

  it("affiche l'erreur de la machine à états sans changer l'écran", async () => {
    simulerApi(() => detail(), {
      ecriture: () =>
        erreurApi("incomplete_dossier", "Le dossier de candidature est incomplet.", 409),
    });
    afficher();

    await userEvent.selectOptions(
      await screen.findByLabelText("Changer le statut"),
      "ready_to_send",
    );
    await userEvent.click(screen.getByRole("button", { name: "Appliquer" }));

    expect(await screen.findByText("Le dossier de candidature est incomplet.")).toBeInTheDocument();
  });

  it("la confirmation d'envoi rappelle que rien n'est envoyé par l'application", async () => {
    const appels = simulerApi(() => detail());
    afficher();

    await userEvent.click(
      await screen.findByRole("button", { name: "J'ai envoyé ma candidature" }),
    );

    const dialogue = await screen.findByRole("dialog", { name: "Confirmer l'envoi" });
    expect(within(dialogue).getByText(/n'envoie jamais rien à votre place/)).toBeInTheDocument();

    await userEvent.type(within(dialogue).getByLabelText("Note (facultatif)"), "Via le portail");
    await userEvent.click(
      within(dialogue).getByRole("button", { name: /Confirmer que je l'ai envoyée/ }),
    );

    await waitFor(() => {
      const envoi = appels.find((a) => a.url.endsWith("/confirm-submission"));
      expect(envoi?.methode).toBe("POST");
      expect(envoi?.corps?.notes).toBe("Via le portail");
      expect(envoi?.corps?.applied_at).toMatch(/Z$/); // date réelle avec fuseau
    });
  });

  it("n'offre plus la confirmation une fois la candidature envoyée", async () => {
    simulerApi(() =>
      detail({
        status: "sent",
        applied_at: "2026-11-03T12:00:00Z",
        can_confirm_submission: false,
        allowed_transitions: ["pending", "interview", "abandoned"],
      }),
    );
    afficher();

    expect(await screen.findByText(/Envoyée le/)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "J'ai envoyé ma candidature" }),
    ).not.toBeInTheDocument();
  });

  it("liste les pièces manquantes du dossier et ses avertissements de qualité", async () => {
    simulerApi(() => detail(), {
      dossier: dossier({
        warnings: ["CV : l'audit de qualité n'est pas conforme (score 55/100)."],
      }),
    });
    afficher();

    const pieces = await screen.findByRole("list", { name: "Pièces du dossier" });
    expect(within(pieces).getByText("CV personnalisé : manquant")).toBeInTheDocument();
    expect(within(pieces).getByText("Lettre de motivation : manquant")).toBeInTheDocument();
    expect(within(pieces).getByText("Lien de candidature : présent")).toBeInTheDocument();
    expect(screen.getByText(/audit de qualité n'est pas conforme/)).toBeInTheDocument();
    expect(screen.getByText(/Le dossier est incomplet/)).toBeInTheDocument();
  });

  it("associe les versions choisies et affiche celles déjà retenues", async () => {
    const appels = simulerApi(
      () =>
        detail({
          documents: [
            {
              document_version_id: "v9",
              document_id: "d9",
              kind: "cv",
              title: "CV Python",
              version: 2,
              quality_passed: false,
              quality_score: 55,
              is_current: true,
            },
          ],
        }),
      {
        lettres: [{ id: "d1", title: "Lettre Acme", versions: [{ id: "v3", version: 1 }] }],
      },
    );
    afficher();

    const associes = await screen.findByRole("list", { name: "Documents associés" });
    expect(within(associes).getByText(/CV Python — v2/)).toBeInTheDocument();
    expect(within(associes).getByText("Retenue")).toBeInTheDocument();
    expect(within(associes).getByText("Audit non conforme")).toBeInTheDocument();

    await waitFor(() =>
      expect(screen.getByRole("option", { name: "Lettre Acme — v1" })).toBeInTheDocument(),
    );
    await userEvent.selectOptions(screen.getByLabelText("Version de la lettre"), "v3");
    await userEvent.click(screen.getByRole("button", { name: "Associer" }));

    await waitFor(() =>
      expect(appels.find((a) => a.methode === "PUT")?.corps).toEqual({
        cv_version_id: null,
        letter_version_id: "v3",
      }),
    );
  });

  it("ajoute une note à l'historique", async () => {
    const appels = simulerApi(() => detail());
    afficher();

    await userEvent.type(await screen.findByLabelText("Nouvelle note"), "Bon contact");
    await userEvent.click(screen.getByRole("button", { name: "Ajouter la note" }));

    await waitFor(() =>
      expect(appels.find((a) => a.url.endsWith("/notes"))?.corps).toEqual({ body: "Bon contact" }),
    );
  });

  it("ajoute un contact en n'envoyant que les champs renseignés", async () => {
    const appels = simulerApi(() => detail());
    afficher();

    await userEvent.type(await screen.findByLabelText("Nom"), "Marc Lemoine");
    await userEvent.type(screen.getByLabelText("E-mail (facultatif)"), "marc@acme.test");
    await userEvent.click(screen.getByRole("button", { name: "Ajouter le contact" }));

    await waitFor(() =>
      expect(appels.find((a) => a.url.endsWith("/contacts"))?.corps).toEqual({
        name: "Marc Lemoine",
        email: "marc@acme.test",
      }),
    );
  });

  it("ne propose de planifier une relance qu'une fois la candidature envoyée", async () => {
    simulerApi(() => detail());
    afficher();

    expect(
      await screen.findByText(/se planifie une fois la candidature envoyée/),
    ).toBeInTheDocument();
    expect(screen.queryByRole("form", { name: "Planifier une relance" })).not.toBeInTheDocument();
  });

  it("planifie puis annule une relance sur une candidature envoyée", async () => {
    const appels = simulerApi(() =>
      detail({
        status: "sent",
        applied_at: "2026-11-03T12:00:00Z",
        can_confirm_submission: false,
        follow_up_at: "2099-01-01T12:00:00Z",
      }),
    );
    afficher();

    expect(await screen.findByText(/Prévue le/)).toBeInTheDocument();
    expect(screen.queryByText("Échue")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Annuler la relance" }));

    await waitFor(() =>
      expect(appels.find((a) => a.url.endsWith("/follow-up"))?.corps).toEqual({
        follow_up_at: null,
      }),
    );
  });

  it("indique une candidature introuvable sans proposer de réessayer", async () => {
    simulerApi(() => erreurApi("application_not_found", "Candidature c1 introuvable.", 404));
    afficher();

    expect(await screen.findByText("Candidature introuvable")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Réessayer" })).not.toBeInTheDocument();
  });
});
