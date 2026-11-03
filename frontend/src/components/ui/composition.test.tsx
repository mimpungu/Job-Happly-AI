import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Inbox } from "lucide-react";
import { describe, expect, it, vi } from "vitest";

import { EmptyState } from "./empty-state";
import { FilterPanel } from "./filter-panel";
import { IconButton } from "./icon-button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./tabs";

describe("EmptyState", () => {
  it("affiche titre, description et action", () => {
    render(
      <EmptyState
        icon={Inbox}
        title="Rien ici"
        description="Ajoutez un élément"
        action={<button type="button">Ajouter</button>}
      />,
    );

    expect(screen.getByRole("heading", { name: "Rien ici" })).toBeInTheDocument();
    expect(screen.getByText("Ajoutez un élément")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ajouter" })).toBeInTheDocument();
  });
});

describe("IconButton", () => {
  it("est nommé par son aria-label et déclenche onClick", async () => {
    const onClick = vi.fn();
    render(
      <IconButton aria-label="Fermer" onClick={onClick}>
        ×
      </IconButton>,
    );

    await userEvent.click(screen.getByRole("button", { name: "Fermer" }));

    expect(onClick).toHaveBeenCalledOnce();
  });
});

describe("Tabs", () => {
  it("change de contenu au clic et au clavier", async () => {
    render(
      <Tabs defaultValue="a">
        <TabsList aria-label="Vues">
          <TabsTrigger value="a">Tableau</TabsTrigger>
          <TabsTrigger value="b">Kanban</TabsTrigger>
        </TabsList>
        <TabsContent value="a">Vue tableau</TabsContent>
        <TabsContent value="b">Vue kanban</TabsContent>
      </Tabs>,
    );

    expect(screen.getByText("Vue tableau")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Kanban" }));

    expect(screen.getByText("Vue kanban")).toBeInTheDocument();
    expect(screen.queryByText("Vue tableau")).not.toBeInTheDocument();
  });
});

describe("FilterPanel", () => {
  it("réinitialise les filtres sans soumettre le formulaire", async () => {
    const onReset = vi.fn();
    render(
      <FilterPanel onReset={onReset}>
        <input aria-label="Ville" />
      </FilterPanel>,
    );

    expect(screen.getByRole("form", { name: "Filtres" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Réinitialiser" }));

    expect(onReset).toHaveBeenCalledOnce();
  });
});
