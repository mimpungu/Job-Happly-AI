import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StorageBackupPanel } from "./storage-backup-panel";

describe("StorageBackupPanel", () => {
  it("dit où sont les données et comment les sauvegarder, sans bouton trompeur", () => {
    render(<StorageBackupPanel />);

    expect(screen.getByText(/Vos données restent sur cette machine/)).toBeInTheDocument();
    expect(screen.getByText(/backup\.sh/)).toBeInTheDocument();
    expect(screen.getByText(/copie hors de cette machine/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Espace CV" })).toHaveAttribute("href", "/cv-studio");
    // Information seulement : l'application ne lance aucune sauvegarde.
    expect(screen.queryByRole("button")).toBeNull();
  });
});
