import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Button } from "./button";

describe("Button", () => {
  it("déclenche onClick", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Valider</Button>);

    await userEvent.click(screen.getByRole("button", { name: "Valider" }));

    expect(onClick).toHaveBeenCalledOnce();
  });

  it("n'est pas un bouton de soumission par défaut", () => {
    render(<Button>Annuler</Button>);

    expect(screen.getByRole("button")).toHaveAttribute("type", "button");
  });

  it("bloque les clics et signale l'occupation pendant le chargement", async () => {
    const onClick = vi.fn();
    render(
      <Button loading onClick={onClick}>
        Envoyer
      </Button>,
    );
    const bouton = screen.getByRole("button", { name: "Envoyer" });

    await userEvent.click(bouton);

    expect(bouton).toBeDisabled();
    expect(bouton).toHaveAttribute("aria-busy", "true");
    expect(onClick).not.toHaveBeenCalled();
  });

  it("reste inactif quand il est désactivé", () => {
    render(<Button disabled>Supprimer</Button>);

    expect(screen.getByRole("button")).toBeDisabled();
  });
});
