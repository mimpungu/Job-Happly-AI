import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ManualOfferDialog, adresseValide } from "./manual-offer-dialog";

const json = (corps: unknown, statut = 200) =>
  new Response(JSON.stringify(corps), { status: statut });

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ManualOfferDialog />
    </QueryClientProvider>,
  );
}

const TEXTE = "Vous rejoignez la direction des systèmes d'information pour développer en Java.";

async function remplir(
  user: ReturnType<typeof userEvent.setup>,
  url = "https://group.bnpparibas/o/1",
) {
  await user.click(screen.getByRole("button", { name: "Ajouter une offre" }));
  await user.type(screen.getByLabelText("Intitulé du poste"), "Développeur Java");
  await user.type(screen.getByLabelText("Entreprise (facultatif)"), "BNP Paribas");
  await user.type(screen.getByLabelText("Lieu (facultatif)"), "Paris, France");
  await user.type(screen.getByLabelText("Adresse de l'offre"), url);
  await user.click(screen.getByLabelText("Texte de l'offre"));
  await user.paste(TEXTE);
}

afterEach(() => vi.unstubAllGlobals());

describe("adresseValide", () => {
  it("n'accepte que le https sans identifiants", () => {
    expect(adresseValide("https://group.bnpparibas/o/1")).toBe(true);
    expect(adresseValide("http://group.bnpparibas/o/1")).toBe(false);
    expect(adresseValide("https://u:p@x.test/o")).toBe(false);
    expect(adresseValide("pas une adresse")).toBe(false);
  });
});

describe("ManualOfferDialog", () => {
  it("n'active l'ajout qu'avec un intitulé, une adresse https et un texte suffisant", async () => {
    afficher();
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Ajouter une offre" }));
    expect(screen.getByRole("button", { name: "Ajouter" })).toBeDisabled();
    await user.type(screen.getByLabelText("Adresse de l'offre"), "http://x.test/o");

    expect(screen.getByText("Saisissez une adresse en https://.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ajouter" })).toBeDisabled();
  });

  it("envoie la saisie et confirme l'ajout", async () => {
    const corps: unknown[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: string, init?: RequestInit) => {
        corps.push(JSON.parse(String(init?.body)));
        return json(
          { offer_id: "o1", created: true, merged: false, changed: false, already_known: false },
          201,
        );
      }),
    );
    afficher();
    const user = userEvent.setup();

    await remplir(user);
    await user.click(screen.getByRole("button", { name: "Ajouter" }));

    await waitFor(() =>
      expect(corps).toEqual([
        {
          title: "Développeur Java",
          company_name: "BNP Paribas",
          location: "Paris, France",
          application_url: "https://group.bnpparibas/o/1",
          description: TEXTE,
        },
      ]),
    );
    expect(await screen.findByRole("status")).toHaveTextContent("Offre ajoutée");
    expect(screen.getByRole("link", { name: "Voir l'offre" })).toHaveAttribute("href", "/jobs/o1");
  });

  it("signale une offre déjà enregistrée au lieu d'en créer une seconde", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          json(
            { offer_id: "o1", created: false, merged: false, changed: false, already_known: true },
            201,
          ),
        ),
    );
    afficher();
    const user = userEvent.setup();

    await remplir(user);
    await user.click(screen.getByRole("button", { name: "Ajouter" }));

    expect(await screen.findByRole("status")).toHaveTextContent("déjà enregistrée");
  });

  it("affiche le message du serveur en cas de refus", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          json(
            { error: { code: "manual_offer_invalid", message: "L'intitulé est obligatoire." } },
            422,
          ),
        ),
    );
    afficher();
    const user = userEvent.setup();

    await remplir(user);
    await user.click(screen.getByRole("button", { name: "Ajouter" }));

    expect(await screen.findByText("L'intitulé est obligatoire.")).toBeInTheDocument();
  });
});
