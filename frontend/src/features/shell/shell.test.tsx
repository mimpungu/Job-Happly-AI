import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
let pathname = "/jobs";

vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
  useRouter: () => ({ push }),
}));

import { GlobalSearch } from "./global-search";
import { Header } from "./header";
import { PageHeading } from "./page-heading";
import { SidebarNav } from "./sidebar-nav";
import { THEME_STORAGE_KEY } from "./theme";
import { ThemeToggle } from "./theme-toggle";

function avecClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
  push.mockClear();
  pathname = "/jobs";
  document.documentElement.dataset.theme = "dark";
  localStorage.clear();
});

afterEach(() => {
  delete document.documentElement.dataset.theme;
});

describe("SidebarNav", () => {
  it("affiche toutes les entrées et marque la page courante", () => {
    render(<SidebarNav />);
    const nav = screen.getByRole("navigation", { name: "Navigation principale" });

    expect(within(nav).getAllByRole("link")).toHaveLength(9);
    expect(within(nav).getByRole("link", { name: "Recherche d'emploi" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(within(nav).getByRole("link", { name: "Candidatures" })).not.toHaveAttribute(
      "aria-current",
    );
  });

  it("conserve toutes les sections de la barre latérale, dans leur ordre", () => {
    render(<SidebarNav />);
    const libelles = within(screen.getByRole("navigation"))
      .getAllByRole("link")
      .map((l) => l.textContent);

    expect(libelles).toEqual([
      "Tableau de bord",
      "Recherche d'emploi",
      "Offres sauvegardées",
      "Espace CV",
      "Lettres de motivation",
      "Candidatures",
      "Préparation d'entretien",
      "Centre IA",
      "Paramètres",
    ]);
  });

  it("range Paramètres en bas de la colonne", () => {
    render(<SidebarNav />);
    const parametres = screen.getByRole("link", { name: "Paramètres" }).closest("li");
    const recherche = screen.getByRole("link", { name: "Recherche d'emploi" }).closest("li");

    expect(parametres).toHaveClass("mt-auto");
    expect(recherche).not.toHaveClass("mt-auto");
  });

  it("notifie la navigation (fermeture du tiroir mobile)", async () => {
    const onNavigate = vi.fn();
    render(<SidebarNav onNavigate={onNavigate} />);

    await userEvent.click(screen.getByRole("link", { name: "Paramètres" }));

    expect(onNavigate).toHaveBeenCalledOnce();
  });
});

describe("GlobalSearch", () => {
  it("lance la recherche vers la page de recherche, terme encodé", async () => {
    render(<GlobalSearch />);

    await userEvent.type(
      screen.getByRole("searchbox", { name: "Recherche globale" }),
      "data & ia{Enter}",
    );

    expect(push).toHaveBeenCalledWith("/jobs?q=data%20%26%20ia");
  });

  it("ignore une recherche vide", async () => {
    render(<GlobalSearch />);

    await userEvent.type(screen.getByRole("searchbox"), "   {Enter}");

    expect(push).not.toHaveBeenCalled();
  });

  it("ferme le tiroir mobile après une recherche", async () => {
    const onNavigate = vi.fn();
    render(<GlobalSearch onNavigate={onNavigate} />);

    await userEvent.type(screen.getByRole("searchbox"), "python{Enter}");

    expect(onNavigate).toHaveBeenCalledOnce();
  });

  it("la touche « / » place le curseur dans le champ", async () => {
    render(
      <>
        <button>Autre</button>
        <GlobalSearch />
      </>,
    );

    await userEvent.keyboard("/");

    expect(screen.getByRole("searchbox")).toHaveFocus();
  });

  it("la touche « / » reste un caractère ordinaire dans un autre champ", async () => {
    render(
      <>
        <input aria-label="Autre champ" />
        <GlobalSearch />
      </>,
    );

    await userEvent.type(screen.getByLabelText("Autre champ"), "a/b");

    expect(screen.getByLabelText("Autre champ")).toHaveValue("a/b");
    expect(screen.getByRole("searchbox")).not.toHaveFocus();
  });
});

describe("Header", () => {
  it("propose l'action principale d'ajout d'offre sur toutes les pages", () => {
    avecClient(<Header />);

    expect(screen.getByRole("button", { name: "Ajouter une offre" })).toBeInTheDocument();
  });

  it("indique honnêtement l'absence de notification", async () => {
    avecClient(<Header />);

    await userEvent.click(screen.getByRole("button", { name: "Notifications" }));

    expect(await screen.findByText("Aucune notification.")).toBeInTheDocument();
  });

  it("donne accès au profil et aux paramètres depuis le menu du profil", async () => {
    avecClient(<Header />);

    await userEvent.click(screen.getByRole("button", { name: "Profil" }));

    expect(await screen.findByRole("menuitem", { name: "Paramètres" })).toHaveAttribute(
      "href",
      "/settings",
    );
    expect(screen.getByRole("menuitem", { name: "Mon profil" })).toHaveAttribute(
      "href",
      "/cv-studio",
    );
  });

  it("réserve l'emplacement du titre de page", () => {
    const { container } = avecClient(<Header />);
    expect(container.querySelector("#page-heading")).toBeInTheDocument();
  });
});

describe("PageHeading", () => {
  it("rend le titre dans l'emplacement de l'en-tête", () => {
    avecClient(
      <>
        <Header />
        <PageHeading title="Bon retour" subtitle="Sous-titre" />
      </>,
    );

    expect(screen.getByRole("heading", { level: 1, name: "Bon retour" })).toBeInTheDocument();
    const emplacement = document.getElementById("page-heading") as HTMLElement;
    expect(within(emplacement).getByText("Sous-titre")).toBeInTheDocument();
  });

  it("ne rend rien sans emplacement (hors coque)", () => {
    render(<PageHeading title="Orphelin" />);
    expect(screen.queryByRole("heading")).not.toBeInTheDocument();
  });
});

describe("ThemeToggle", () => {
  it("bascule vers le thème clair et mémorise le choix", async () => {
    render(<ThemeToggle />);

    await userEvent.click(screen.getByRole("button", { name: "Passer au thème clair" }));

    expect(document.documentElement.dataset.theme).toBe("light");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
    expect(screen.getByRole("button", { name: "Passer au thème sombre" })).toBeInTheDocument();
  });

  it("revient au thème sombre", async () => {
    document.documentElement.dataset.theme = "light";
    render(<ThemeToggle />);

    await userEvent.click(screen.getByRole("button", { name: "Passer au thème sombre" }));

    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
  });

  it("suit un changement de thème fait ailleurs", async () => {
    render(<ThemeToggle />);

    await act(async () => {
      document.documentElement.dataset.theme = "light";
    });

    expect(
      await screen.findByRole("button", { name: "Passer au thème sombre" }),
    ).toBeInTheDocument();
  });

  it("fonctionne même si le stockage du navigateur est refusé", async () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("quota");
    });
    render(<ThemeToggle />);

    await userEvent.click(screen.getByRole("button", { name: "Passer au thème clair" }));

    expect(document.documentElement.dataset.theme).toBe("light");
    vi.restoreAllMocks();
  });
});
