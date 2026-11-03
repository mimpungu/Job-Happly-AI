import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
let pathname = "/jobs";

vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
  useRouter: () => ({ push }),
}));

import { Header } from "./header";
import { SidebarNav } from "./sidebar-nav";

beforeEach(() => {
  push.mockClear();
  pathname = "/jobs";
});

describe("SidebarNav", () => {
  it("affiche tous les liens et marque la page courante", () => {
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

  it("notifie la navigation (fermeture du tiroir mobile)", async () => {
    const onNavigate = vi.fn();
    render(<SidebarNav onNavigate={onNavigate} />);

    await userEvent.click(screen.getByRole("link", { name: "Paramètres" }));

    expect(onNavigate).toHaveBeenCalledOnce();
  });
});

describe("Header", () => {
  it("lance la recherche globale vers la page de recherche, terme encodé", async () => {
    render(<Header />);

    await userEvent.type(
      screen.getByRole("searchbox", { name: "Recherche globale" }),
      "data & ia{Enter}",
    );

    expect(push).toHaveBeenCalledWith("/jobs?q=data%20%26%20ia");
  });

  it("ignore une recherche vide", async () => {
    render(<Header />);

    await userEvent.type(screen.getByRole("searchbox"), "   {Enter}");

    expect(push).not.toHaveBeenCalled();
  });

  it("indique honnêtement l'absence de notification", async () => {
    render(<Header />);

    await userEvent.click(screen.getByRole("button", { name: "Notifications" }));

    expect(await screen.findByText("Aucune notification.")).toBeInTheDocument();
  });

  it("donne accès aux paramètres depuis le profil", async () => {
    render(<Header />);

    await userEvent.click(screen.getByRole("button", { name: "Profil" }));

    expect(await screen.findByRole("menuitem", { name: "Paramètres" })).toHaveAttribute(
      "href",
      "/settings",
    );
  });
});
