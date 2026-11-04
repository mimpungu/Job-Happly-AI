import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Toaster } from "@/components/ui/toaster";
import { LocaleProvider, useLocaleSetting } from "@/i18n/locale-provider";

import { GeneralSettingsPanel } from "./general-settings-panel";

const json = (corps: unknown, statut = 200) =>
  new Response(JSON.stringify(corps), { status: statut });

const PREFS = {
  ui_language: "fr",
  country_code: null,
  currency: null,
  timezone: null,
  willing_to_relocate: null,
  target_countries: [],
  work_permit_countries: [],
  needs_sponsorship: null,
  supported_ui_languages: ["fr", "en"],
};

function simuler(prefs = PREFS) {
  const appels: { url: string; methode: string; corps?: string }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      appels.push({ url, methode: init?.method ?? "GET", corps: init?.body as string | undefined });
      if (url.includes("/reference/countries")) {
        return json([
          { code: "CA", name: "Canada", official_languages: ["en", "fr"], currencies: ["CAD"] },
          { code: "FR", name: "France", official_languages: ["fr"], currencies: ["EUR"] },
        ]);
      }
      if (url.includes("/reference/currencies")) {
        return json([{ code: "CAD", name: "dollar canadien", symbol: "$CA" }]);
      }
      if (url.includes("/reference/timezones")) return json(["America/Toronto", "Europe/Paris"]);
      if ((init?.method ?? "GET") === "PUT")
        return json({ ...prefs, ...JSON.parse(init!.body as string) });
      return json(prefs);
    }),
  );
  return appels;
}

function SondeLangue() {
  const { locale } = useLocaleSetting();
  return <p data-testid="langue">{locale}</p>;
}

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <LocaleProvider>
        <GeneralSettingsPanel />
        <SondeLangue />
        <Toaster />
      </LocaleProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("GeneralSettingsPanel", () => {
  it("enregistre les préférences et applique aussitôt la langue choisie", async () => {
    const appels = simuler();
    afficher();

    await userEvent.selectOptions(await screen.findByLabelText("Langue de l'interface"), "en");
    await userEvent.selectOptions(
      await screen.findByLabelText("Pays de recherche principal"),
      "CA",
    );
    await userEvent.type(screen.getByLabelText("Pays où je pourrais travailler"), "fr, de, fr");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    await waitFor(() => expect(screen.getByTestId("langue")).toHaveTextContent("en"));
    const ecriture = appels.find((a) => a.methode === "PUT");
    expect(JSON.parse(ecriture?.corps ?? "{}")).toMatchObject({
      ui_language: "en",
      country_code: "CA",
      target_countries: ["FR", "DE"],
      willing_to_relocate: null,
    });
    // L'interface est passée en anglais, et le choix est retenu pour la prochaine visite.
    expect(await screen.findByText("General settings")).toBeInTheDocument();
    expect(localStorage.getItem("happly-locale")).toBe("en");
  });

  it("distingue « non » de « non renseigné » pour le parrainage de visa", async () => {
    const appels = simuler();
    afficher();

    await userEvent.selectOptions(
      await screen.findByLabelText("Besoin d'un parrainage de visa"),
      "no",
    );
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    await waitFor(() => expect(appels.some((a) => a.methode === "PUT")).toBe(true));
    const ecriture = appels.find((a) => a.methode === "PUT");
    expect(JSON.parse(ecriture?.corps ?? "{}").needs_sponsorship).toBe(false);
  });

  it("affiche l'erreur du serveur si le chargement échoue", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        json({ error: { code: "internal_error", message: "Erreur interne." } }, 500),
      ),
    );
    afficher();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Impossible de charger vos préférences",
    );
  });

  it("renvoie vers le profil, dans la langue choisie", async () => {
    simuler();
    afficher();

    expect(
      await screen.findByRole("link", { name: "Modifier mon profil (Espace CV)" }),
    ).toHaveAttribute("href", "/cv-studio");
  });

  it("retrouve la langue enregistrée au montage", async () => {
    localStorage.setItem("happly-locale", "en");
    simuler({ ...PREFS, ui_language: "en" });
    afficher();

    await waitFor(() => expect(screen.getByTestId("langue")).toHaveTextContent("en"));
    expect(document.documentElement.lang).toBe("en");
  });
});
