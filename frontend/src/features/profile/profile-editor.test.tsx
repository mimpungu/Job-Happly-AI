import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Toaster } from "@/components/ui/toaster";
import type { ProfileDocument, StoredProfile } from "@/types/profile";

import { emptyDocument, NEW_ITEMS } from "./draft";
import { ProfileEditor } from "./profile-editor";

const json = (corps: unknown, statut = 200) =>
  new Response(JSON.stringify(corps), { status: statut });

function document_(surcharge: Partial<ProfileDocument> = {}): ProfileDocument {
  return { ...emptyDocument(), ...surcharge };
}

const importee = (): ProfileDocument =>
  document_({
    identity: { ...emptyDocument().identity, first_name: "Marie", last_name: "Dupont" },
    experiences: [
      {
        ...NEW_ITEMS.experiences(),
        origin: "imported",
        source_text: "Développeuse Python\n2021 - Aujourd'hui",
        title: "Développeuse Python",
        company: null, // non lue par l'extraction
        start: { year: 2021, month: null },
        is_current: true,
      },
    ],
    skills: [{ ...NEW_ITEMS.skills(), origin: "imported", name: "Python", source_text: "Python" }],
    languages: [
      {
        ...NEW_ITEMS.languages(),
        origin: "imported",
        language_code: "es",
        level_text: "notions scolaires",
        source_text: "Espagnol - notions scolaires",
      },
    ],
  });

const stocke = (
  document: ProfileDocument,
  statut: "draft" | "validated" = "draft",
  version = 1,
): StoredProfile => ({
  meta: {
    id: "p1",
    version,
    status: statut,
    created_at: "2026-11-04T09:00:00Z",
    updated_at: `2026-11-04T09:0${version}:00Z`,
    validated_at: statut === "validated" ? "2026-11-04T09:10:00Z" : null,
  },
  document,
});

interface Appel {
  url: string;
  methode: string;
  corps?: unknown;
}

/** API locale simulée : jamais le réseau réel. `etat` est le profil serveur courant. */
function simulerApi(
  initial: StoredProfile | null,
  surcharges: Partial<Record<string, (corps: unknown) => Response>> = {},
) {
  let etat = initial;
  const appels: Appel[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const methode = init?.method ?? "GET";
      const corps =
        typeof init?.body === "string"
          ? (JSON.parse(init.body) as unknown)
          : (init?.body ?? undefined);
      appels.push({ url, methode, corps });
      const cle = `${methode} ${url.replace(/^.*\/api\/v1/, "")}`;
      const surcharge = surcharges[cle];
      if (surcharge) return surcharge(corps);
      switch (cle) {
        case "GET /profile":
          return json(etat);
        case "PUT /profile/draft": {
          etat = stocke(corps as ProfileDocument, "draft", etat?.meta.version ?? 1);
          return json(etat);
        }
        case "POST /profile/validate":
          etat = etat ? stocke(etat.document, "validated", etat.meta.version) : etat;
          return json(etat);
        case "POST /profile/versions":
          etat = stocke(etat?.document ?? emptyDocument(), "draft", (etat?.meta.version ?? 0) + 1);
          return json(etat, 201);
        case "GET /profile/history?limit=100":
          return json([]);
        default:
          return json({ error: { code: "x", message: `Route non simulée : ${cle}` } }, 500);
      }
    }),
  );
  return appels;
}

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ProfileEditor />
      <Toaster />
    </QueryClientProvider>,
  );
}

const fichierCv = () => new File(["Marie Dupont\n…"], "cv.txt", { type: "text/plain" });

function simulerImport(proposition: ProfileDocument, avertissements: string[] = []) {
  return {
    "POST /profile/import": () =>
      json({
        filename: "cv.txt",
        format: "txt",
        page_count: null,
        warnings: avertissements,
        text: "…",
        proposed_document: proposition,
      }),
  };
}

afterEach(() => vi.unstubAllGlobals());

describe("ProfileEditor — démarrage", () => {
  it("affiche le titre de la page dès le chargement", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => undefined)),
    ); // jamais résolu
    afficher();

    expect(screen.getByRole("heading", { level: 1, name: "Espace CV" })).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "Chargement du profil" })).toBeInTheDocument();
  });

  it("propose d'importer ou de saisir à la main quand il n'y a pas de profil", async () => {
    simulerApi(null);
    afficher();

    expect(await screen.findByText("Aucun CV maître")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Importer un CV" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Saisir à la main" }));

    expect(screen.getByText("Non enregistré")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Identité" })).toBeInTheDocument();
  });

  it("affiche l'erreur de chargement avec un bouton pour réessayer", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fetch failed")));
    afficher();

    expect(await screen.findByText("Impossible de charger le profil")).toBeInTheDocument();
    // Le titre de la page reste présent dans l'état d'erreur.
    expect(screen.getByRole("heading", { level: 1, name: "Espace CV" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Réessayer" })).toBeInTheDocument();
  });

  it("charge un brouillon existant", async () => {
    simulerApi(stocke(document_({ skills: [{ ...NEW_ITEMS.skills(), name: "SQL" }] })));
    afficher();

    expect(await screen.findByText("Version 1 · brouillon")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Compétences (1)" })).toBeInTheDocument();
  });
});

describe("ProfileEditor — import et relecture", () => {
  it("l'import produit un brouillon non enregistré dont chaque élément est à confirmer", async () => {
    const appels = simulerApi(
      null,
      simulerImport(importee(), ["Encodage non UTF-8 : vérifiez les accents."]),
    );
    afficher();
    await screen.findByText("Aucun CV maître");

    await userEvent.upload(screen.getByLabelText("Fichier du CV à importer"), fichierCv());

    expect(await screen.findByText("3 éléments à confirmer")).toBeInTheDocument();
    expect(screen.getByText("Modifications non enregistrées")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Encodage non UTF-8");
    // L'import seul n'enregistre rien.
    expect(appels.some((a) => a.methode === "PUT")).toBe(false);
  });

  it("montre l'extrait source, l'état incomplet et n'autorise la confirmation qu'une fois complété", async () => {
    simulerApi(null, simulerImport(importee()));
    afficher();
    await screen.findByText("Aucun CV maître");
    await userEvent.upload(screen.getByLabelText("Fichier du CV à importer"), fichierCv());
    await userEvent.click(await screen.findByRole("tab", { name: /Expériences/ }));

    const carte = within(
      screen.getByRole("region", { name: "Expériences professionnelles" }),
    ).getByRole("listitem");
    expect(within(carte).getByText("Importé")).toBeInTheDocument();
    expect(within(carte).getByText("Incomplet")).toBeInTheDocument();
    expect(within(carte).getByText(/À renseigner pour confirmer : entreprise/)).toBeInTheDocument();
    expect(within(carte).getByText(/Développeuse Python\s+2021/)).toBeInTheDocument();
    const confirmer = within(carte).getByRole("button", {
      name: /Confirmer : Développeuse Python/,
    });
    expect(confirmer).toBeDisabled();

    await userEvent.type(within(carte).getByLabelText("Entreprise"), "Exemple SA");
    expect(confirmer).toBeEnabled();
    await userEvent.click(confirmer);

    expect(within(carte).getByText("Confirmé")).toBeInTheDocument();
    expect(within(carte).queryByText("Incomplet")).toBeNull();
  });

  it("modifier un élément confirmé exige une nouvelle confirmation", async () => {
    simulerApi(null, simulerImport(importee()));
    afficher();
    await screen.findByText("Aucun CV maître");
    await userEvent.upload(screen.getByLabelText("Fichier du CV à importer"), fichierCv());
    await userEvent.click(await screen.findByRole("tab", { name: /Compétences/ }));
    const carte = within(screen.getByRole("region", { name: "Compétences" })).getByRole("listitem");
    await userEvent.click(within(carte).getByRole("button", { name: /Confirmer : Python/ }));
    expect(within(carte).getByText("Confirmé")).toBeInTheDocument();

    await userEvent.type(within(carte).getByLabelText("Catégorie"), "Langage");

    expect(within(carte).getByText("À confirmer")).toBeInTheDocument();
  });

  it("un niveau de langue vague n'est pas converti : l'utilisateur doit choisir", async () => {
    simulerApi(null, simulerImport(importee()));
    afficher();
    await screen.findByText("Aucun CV maître");
    await userEvent.upload(screen.getByLabelText("Fichier du CV à importer"), fichierCv());
    await userEvent.click(await screen.findByRole("tab", { name: /Langues/ }));
    const langue = screen.getByRole("region", { name: "Langues" });

    expect(within(langue).getByText(/Dans le CV : « notions scolaires »/)).toBeInTheDocument();
    expect(within(langue).getByLabelText("Niveau")).toHaveValue("");
    expect(within(langue).getByRole("button", { name: /Confirmer : ES/ })).toBeDisabled();

    await userEvent.selectOptions(within(langue).getByLabelText("Niveau"), "a2");

    expect(within(langue).getByRole("button", { name: /Confirmer : ES/ })).toBeEnabled();
  });

  it("demande confirmation avant de remplacer un brouillon qui a du contenu", async () => {
    simulerApi(
      stocke(document_({ skills: [{ ...NEW_ITEMS.skills(), name: "SQL" }] })),
      simulerImport(importee()),
    );
    afficher();
    await screen.findByText("Version 1 · brouillon");

    await userEvent.upload(screen.getByLabelText("Fichier du CV à importer"), fichierCv());

    expect(await screen.findByText("Remplacer le brouillon par ce CV ?")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Remplacer" }));
    expect(await screen.findByText("3 éléments à confirmer")).toBeInTheDocument();
  });

  it("annuler le remplacement garde le brouillon actuel", async () => {
    simulerApi(
      stocke(document_({ skills: [{ ...NEW_ITEMS.skills(), name: "SQL" }] })),
      simulerImport(importee()),
    );
    afficher();
    await screen.findByText("Version 1 · brouillon");
    await userEvent.upload(screen.getByLabelText("Fichier du CV à importer"), fichierCv());

    await userEvent.click(await screen.findByRole("button", { name: "Annuler" }));

    expect(screen.getByRole("tab", { name: "Compétences (1)" })).toBeInTheDocument();
    expect(screen.queryByText("Modifications non enregistrées")).toBeNull();
  });

  it("affiche le message clair d'un CV refusé", async () => {
    simulerApi(null, {
      "POST /profile/import": () =>
        json(
          { error: { code: "document_error", message: "Ce PDF est protégé par un mot de passe." } },
          422,
        ),
    });
    afficher();
    await screen.findByText("Aucun CV maître");

    await userEvent.upload(screen.getByLabelText("Fichier du CV à importer"), fichierCv());

    expect(await screen.findByText("Ce PDF est protégé par un mot de passe.")).toBeInTheDocument();
    expect(screen.getByText("Aucun CV maître")).toBeInTheDocument();
  });
});

describe("ProfileEditor — enregistrement et validation", () => {
  it("enregistre le brouillon puis efface l'indicateur de modification", async () => {
    const appels = simulerApi(null, simulerImport(importee()));
    afficher();
    await screen.findByText("Aucun CV maître");
    await userEvent.upload(screen.getByLabelText("Fichier du CV à importer"), fichierCv());
    await screen.findByText("Modifications non enregistrées");

    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    expect(await screen.findByText("Brouillon enregistré.")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText("Modifications non enregistrées")).toBeNull());
    const ecriture = appels.find((a) => a.methode === "PUT");
    const envoye = ecriture?.corps as ProfileDocument;
    expect(envoye.identity.first_name).toBe("Marie");
    expect(envoye.experiences[0]?.origin).toBe("imported");
    expect(envoye.experiences[0]?.validated).toBe(false);
    expect(screen.getByText("Version 1 · brouillon")).toBeInTheDocument();
  });

  it("n'autorise pas la validation tant que des modifications ne sont pas enregistrées", async () => {
    simulerApi(stocke(document_()));
    afficher();
    await screen.findByText("Version 1 · brouillon");
    const valider = screen.getByRole("button", { name: "Valider le profil" });
    expect(valider).toBeEnabled();

    await userEvent.click(screen.getByRole("tab", { name: "Identité" }));
    await userEvent.type(screen.getByLabelText("Prénom"), "Marie");

    expect(valider).toBeDisabled();
    expect(screen.getByRole("button", { name: "Enregistrer" })).toBeEnabled();
  });

  it("affiche en français les champs bloquant la validation", async () => {
    simulerApi(stocke(document_()), {
      "POST /profile/validate": () =>
        json(
          {
            error: {
              code: "profile_incomplete",
              message: "Le profil est incomplet.",
              details: [
                { field: "identity.first_name", message: "Prénom obligatoire." },
                {
                  field: "experiences[0]",
                  message: "Élément non confirmé : relisez-le et validez-le.",
                },
                { field: "languages.1.proficiency", message: "Champ obligatoire." },
              ],
            },
          },
          422,
        ),
    });
    afficher();
    await screen.findByText("Version 1 · brouillon");

    await userEvent.click(screen.getByRole("button", { name: "Valider le profil" }));

    const alerte = await screen.findByRole("alert");
    expect(alerte).toHaveTextContent("Identité : prénom — Prénom obligatoire.");
    expect(alerte).toHaveTextContent("Expérience 1 — Élément non confirmé");
    expect(alerte).toHaveTextContent("Langue 2 : niveau — Champ obligatoire.");
  });

  it("une erreur d'enregistrement affiche les champs refusés", async () => {
    simulerApi(null, {
      ...simulerImport(importee()),
      "PUT /profile/draft": () =>
        json(
          {
            error: {
              code: "validation_error",
              message: "Les données envoyées sont invalides.",
              details: [{ field: "identity.email", message: "Adresse e-mail invalide." }],
            },
          },
          422,
        ),
    });
    afficher();
    await screen.findByText("Aucun CV maître");
    await userEvent.upload(screen.getByLabelText("Fichier du CV à importer"), fichierCv());
    await screen.findByText("Modifications non enregistrées");

    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Identité : e-mail — Adresse e-mail invalide.",
    );
    expect(screen.getByText("Modifications non enregistrées")).toBeInTheDocument();
  });

  it("valide le profil", async () => {
    simulerApi(stocke(document_()));
    afficher();
    await screen.findByText("Version 1 · brouillon");

    await userEvent.click(screen.getByRole("button", { name: "Valider le profil" }));

    expect(await screen.findByText("Version 1 · validée")).toBeInTheDocument();
  });
});

describe("ProfileEditor — version validée", () => {
  const validee = () =>
    stocke(
      document_({ skills: [{ ...NEW_ITEMS.skills(), name: "SQL", validated: true }] }),
      "validated",
    );

  it("est en lecture seule et propose une nouvelle version", async () => {
    simulerApi(validee());
    afficher();

    expect(await screen.findByText("Version 1 · validée")).toBeInTheDocument();
    expect(screen.getByText(/ne peut pas être modifiée/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Enregistrer" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Importer un CV" })).toBeNull();
    await userEvent.click(screen.getByRole("tab", { name: "Identité" }));
    expect(screen.getByLabelText("Prénom")).toBeDisabled();
  });

  it("crée la version suivante et la rend modifiable", async () => {
    simulerApi(validee());
    afficher();
    await screen.findByText("Version 1 · validée");

    await userEvent.click(screen.getByRole("button", { name: "Créer une nouvelle version" }));

    expect(await screen.findByText("Version 2 · brouillon")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Identité" }));
    expect(screen.getByLabelText("Prénom")).toBeEnabled();
  });
});

describe("ProfileEditor — préférences", () => {
  it("normalise les listes à la sortie du champ et exige une devise avec un salaire", async () => {
    simulerApi(stocke(document_()));
    afficher();
    await screen.findByText("Version 1 · brouillon");
    await userEvent.click(screen.getByRole("tab", { name: "Préférences" }));

    await userEvent.type(screen.getByLabelText("Pays"), "fr, be, fr");
    await userEvent.tab();
    await userEvent.type(screen.getByLabelText("Salaire annuel souhaité (minimum)"), "45000");

    expect(screen.getByLabelText("Pays")).toHaveValue("FR, BE");
    expect(screen.getByRole("alert")).toHaveTextContent("La devise est obligatoire");

    await userEvent.click(screen.getByLabelText("Hybride"));
    expect(screen.getByLabelText("Hybride")).toBeChecked();
  });
});

describe("ProfileEditor — consultation des versions", () => {
  const v1 = () =>
    stocke(
      document_({ identity: { ...emptyDocument().identity, first_name: "Ancien" } }),
      "validated",
      1,
    );
  const v2 = () =>
    stocke(
      document_({ identity: { ...emptyDocument().identity, first_name: "Courant" } }),
      "draft",
      2,
    );
  const metas = () => [v2().meta, v1().meta];

  it("ne propose pas de sélecteur quand il n'existe qu'une version", async () => {
    simulerApi(v1(), { "GET /profile/versions": () => json([v1().meta]) });
    afficher();
    await screen.findByText("Version 1 · validée");

    expect(screen.queryByLabelText("Version affichée")).toBeNull();
  });

  it("affiche une ancienne version en lecture seule sans toucher au brouillon en cours", async () => {
    const appels = simulerApi(v2(), {
      "GET /profile/versions": () => json(metas()),
      "GET /profile/versions/1": () => json(v1()),
    });
    afficher();
    await screen.findByText("Version 2 · brouillon");
    await userEvent.click(screen.getByRole("tab", { name: "Identité" }));
    // Modification non enregistrée du brouillon actuel.
    await userEvent.clear(screen.getByLabelText("Prénom"));
    await userEvent.type(screen.getByLabelText("Prénom"), "Brouillon modifié");

    await userEvent.selectOptions(await screen.findByLabelText("Version affichée"), "1");

    expect(
      await screen.findByText(/Vous consultez la version 1 en lecture seule/),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Identité" }));
    expect(screen.getByLabelText("Prénom")).toHaveValue("Ancien");
    expect(screen.getByLabelText("Prénom")).toBeDisabled();
    // Aucune action d'écriture n'est proposée pendant la consultation.
    expect(screen.queryByRole("button", { name: "Enregistrer" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Valider le profil" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Importer un CV" })).toBeNull();
    expect(appels.some((a) => a.methode === "PUT")).toBe(false);

    await userEvent.click(screen.getByRole("button", { name: "Revenir à la version actuelle" }));

    await userEvent.click(screen.getByRole("tab", { name: "Identité" }));
    expect(screen.getByLabelText("Prénom")).toHaveValue("Brouillon modifié"); // rien n'a été perdu
    expect(screen.getByText("Modifications non enregistrées")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Enregistrer" })).toBeEnabled();
  });

  it("signale l'échec du chargement d'une version", async () => {
    simulerApi(v2(), {
      "GET /profile/versions": () => json(metas()),
      "GET /profile/versions/1": () =>
        json(
          { error: { code: "profile_not_found", message: "Profil ou version introuvable." } },
          404,
        ),
    });
    afficher();
    await screen.findByText("Version 2 · brouillon");

    await userEvent.selectOptions(await screen.findByLabelText("Version affichée"), "1");

    expect(await screen.findByText("Profil ou version introuvable.")).toBeInTheDocument();
  });
});
