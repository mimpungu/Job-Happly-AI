import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Field, Input, SearchInput } from "./input";

describe("Field et Input", () => {
  it("associe le libellé au champ", () => {
    render(<Field label="Email">{(champ) => <Input {...champ} />}</Field>);

    expect(screen.getByLabelText("Email")).toBeInTheDocument();
  });

  it("affiche l'erreur, marque le champ invalide et le relie à son message", () => {
    render(
      <Field label="Email" error="Adresse invalide" hint="Aide">
        {(champ) => <Input {...champ} />}
      </Field>,
    );
    const champ = screen.getByLabelText("Email");

    expect(champ).toHaveAttribute("aria-invalid", "true");
    expect(champ).toHaveAccessibleDescription("Adresse invalide");
    expect(screen.queryByText("Aide")).not.toBeInTheDocument();
  });

  it("affiche l'aide quand il n'y a pas d'erreur", () => {
    render(
      <Field label="Ville" hint="Ex. Paris">
        {(champ) => <Input {...champ} />}
      </Field>,
    );

    expect(screen.getByLabelText("Ville")).toHaveAccessibleDescription("Ex. Paris");
  });
});

describe("SearchInput", () => {
  it("notifie la saisie puis permet d'effacer", async () => {
    const onValueChange = vi.fn();
    render(<SearchInput aria-label="Recherche" onValueChange={onValueChange} />);

    await userEvent.type(screen.getByRole("searchbox", { name: "Recherche" }), "data");
    expect(onValueChange).toHaveBeenLastCalledWith("data");

    await userEvent.click(screen.getByRole("button", { name: "Effacer la recherche" }));
    expect(onValueChange).toHaveBeenLastCalledWith("");
    expect(screen.getByRole("searchbox")).toHaveValue("");
  });

  it("n'affiche pas le bouton d'effacement quand le champ est vide", () => {
    render(<SearchInput aria-label="Recherche" />);

    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
