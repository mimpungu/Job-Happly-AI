import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Card, CardContent, CardDescription, CardHeader, CardTitle, Panel } from "./card";

describe("Card", () => {
  it("compose titre, description et contenu", () => {
    render(
      <Card>
        <CardHeader>
          <CardTitle>Offres</CardTitle>
          <CardDescription>Résumé</CardDescription>
        </CardHeader>
        <CardContent>Contenu</CardContent>
      </Card>,
    );

    expect(screen.getByRole("heading", { name: "Offres" })).toBeInTheDocument();
    expect(screen.getByText("Résumé")).toBeInTheDocument();
    expect(screen.getByText("Contenu")).toBeInTheDocument();
  });
});

describe("Panel", () => {
  it("est une région nommée par son titre et affiche ses actions", () => {
    render(
      <Panel title="Recherches" actions={<button type="button">Ajouter</button>}>
        Corps
      </Panel>,
    );

    expect(screen.getByRole("region", { name: "Recherches" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ajouter" })).toBeInTheDocument();
  });
});
