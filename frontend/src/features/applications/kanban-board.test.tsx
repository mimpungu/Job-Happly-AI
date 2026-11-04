import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { KanbanView } from "@/types/applications";

import { KanbanBoard } from "./kanban-board";

const item = (id: string, titre: string) => ({
  id,
  status: "to_apply",
  updated_at: "2026-11-04T10:00:00Z",
  offer: { offer_id: `o-${id}`, title: titre, company_name: "Exemple SA" },
});

const vue = {
  columns: [
    { status: "to_apply", count: 2, has_more: false, items: [item("a", "Dev"), item("b", "Data")] },
    { status: "sent", count: 0, has_more: false, items: [] },
    { status: "interview", count: 0, has_more: false, items: [] },
  ],
} as unknown as KanbanView;

describe("KanbanBoard", () => {
  it("répartit les colonnes sur deux rangées qui défilent horizontalement", () => {
    render(<KanbanBoard view={vue} />);

    const tableau = screen.getByRole("group", { name: "Kanban des candidatures" });
    expect(tableau.className).toContain("grid-rows-2");
    expect(tableau.className).toContain("grid-flow-col");
    expect(tableau.className).toContain("overflow-x-auto");
    // Zone défilante : atteignable au clavier.
    expect(tableau).toHaveAttribute("tabindex", "0");
  });

  it("fait défiler verticalement la liste de chaque colonne remplie", () => {
    render(<KanbanBoard view={vue} />);

    const liste = screen.getByRole("list", { name: /Candidatures : / });
    expect(liste.className).toContain("overflow-y-auto");
    expect(liste).toHaveAttribute("tabindex", "0");
    expect(within(liste).getAllByRole("link")).toHaveLength(2);
    // Les colonnes vides n'ont pas de liste défilante inutile.
    expect(screen.getAllByText("Aucune candidature")).toHaveLength(2);
  });
});
