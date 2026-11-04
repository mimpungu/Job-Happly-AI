import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { SpendChart } from "./spend-chart";

const jours = [
  { date: "2026-11-01", cost: "0" },
  { date: "2026-11-02", cost: "0.25" },
  { date: "2026-11-03", cost: "0" },
  { date: "2026-11-04", cost: "0.5" },
];

describe("SpendChart", () => {
  it("résume le graphique pour un lecteur d'écran, jours sans dépense compris", () => {
    render(<SpendChart days={jours} currency="EUR" dailyBudget="1" />);

    const graphique = screen.getByRole("img");
    expect(graphique).toHaveAccessibleName(/0,75 EUR au total sur 4 jours/);
  });

  it("affiche le plafond journalier comme trait de référence étiqueté", () => {
    render(<SpendChart days={jours} currency="EUR" dailyBudget="1" />);

    expect(screen.getByText("Plafond journalier : 1 EUR")).toBeInTheDocument();
  });

  it("n'invente pas de plafond quand il n'est pas défini", () => {
    render(<SpendChart days={jours} currency="EUR" dailyBudget={null} />);

    expect(screen.queryByText(/Plafond journalier/)).toBeNull();
  });

  it("donne la valeur d'un jour au survol", async () => {
    const { container } = render(<SpendChart days={jours} currency="EUR" dailyBudget="1" />);

    const colonnes = container.querySelectorAll("[class*='flex-1'][class*='items-end']");
    await userEvent.hover(colonnes[1] as Element);

    expect(await screen.findByRole("tooltip")).toHaveTextContent("2 nov. : 0,25 EUR");
  });

  it("propose le même contenu en tableau", async () => {
    render(<SpendChart days={jours} currency="EUR" dailyBudget="1" />);

    await userEvent.click(screen.getByRole("button", { name: "Afficher en tableau" }));

    const tableau = screen.getByRole("table");
    expect(within(tableau).getAllByRole("row")).toHaveLength(5); // en-tête + 4 jours
    expect(within(tableau).getByText("0,5 EUR")).toBeInTheDocument();
    expect(screen.queryByRole("img")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Afficher le graphique" }));
    expect(screen.getByRole("img")).toBeInTheDocument();
  });

  it("n'affiche rien sans donnée", () => {
    const { container } = render(<SpendChart days={[]} currency="EUR" dailyBudget={null} />);

    expect(container).toBeEmptyDOMElement();
  });
});
