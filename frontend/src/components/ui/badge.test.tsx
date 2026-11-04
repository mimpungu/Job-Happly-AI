import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { APPLICATION_STATUSES } from "@/types/application-status";

import { Badge } from "./badge";
import { StatusBadge } from "./status-badge";

describe("Badge", () => {
  it("affiche son contenu", () => {
    render(<Badge variant="success">Actif</Badge>);

    expect(screen.getByText("Actif")).toBeInTheDocument();
  });
});

describe("StatusBadge", () => {
  it("fournit un libellé texte pour chacun des statuts de candidature", () => {
    for (const status of APPLICATION_STATUSES) {
      const { container, unmount } = render(<StatusBadge status={status} />);

      expect(container.textContent?.trim()).not.toBe("");
      unmount();
    }
  });

  it("affiche le libellé français du statut", () => {
    render(<StatusBadge status="second_interview" />);

    expect(screen.getByText("Deuxième entretien")).toBeInTheDocument();
  });
});
