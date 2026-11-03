import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Button } from "./button";
import { ConfirmDialog, Dialog, DialogContent, DialogTrigger } from "./dialog";

describe("Dialog", () => {
  it("s'ouvre, expose titre et description, et se ferme avec Échap", async () => {
    render(
      <Dialog>
        <DialogTrigger asChild>
          <Button>Ouvrir</Button>
        </DialogTrigger>
        <DialogContent title="Paramètres" description="Modifier vos préférences">
          Contenu
        </DialogContent>
      </Dialog>,
    );

    await userEvent.click(screen.getByRole("button", { name: "Ouvrir" }));
    const dialogue = screen.getByRole("dialog", { name: "Paramètres" });
    expect(dialogue).toHaveAccessibleDescription("Modifier vos préférences");

    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

describe("ConfirmDialog", () => {
  it("confirme l'action", async () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmDialog
        open
        onOpenChange={() => {}}
        title="Supprimer"
        description="Action irréversible"
        confirmLabel="Supprimer"
        destructive
        onConfirm={onConfirm}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Supprimer" }));

    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("annule sans confirmer", async () => {
    const onConfirm = vi.fn();
    const onOpenChange = vi.fn();
    render(
      <ConfirmDialog
        open
        onOpenChange={onOpenChange}
        title="Supprimer"
        description="Action irréversible"
        confirmLabel="Supprimer"
        onConfirm={onConfirm}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Annuler" }));

    expect(onConfirm).not.toHaveBeenCalled();
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
