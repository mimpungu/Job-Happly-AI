import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Home from "./page";

describe("Page d'accueil", () => {
  it("affiche le titre Happly AI", () => {
    render(<Home />);

    expect(screen.getByRole("heading", { name: "Happly AI" })).toBeInTheDocument();
  });
});
