import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Button } from "./button";
import { Dropdown, DropdownContent, DropdownItem, DropdownTrigger } from "./dropdown";
import { Skeleton } from "./skeleton";
import { Tooltip, TooltipProvider } from "./tooltip";

describe("Dropdown", () => {
  it("ouvre le menu et déclenche l'action choisie", async () => {
    const onSelect = vi.fn();
    render(
      <Dropdown>
        <DropdownTrigger asChild>
          <Button>Actions</Button>
        </DropdownTrigger>
        <DropdownContent>
          <DropdownItem onSelect={onSelect}>Archiver</DropdownItem>
        </DropdownContent>
      </Dropdown>,
    );

    await userEvent.click(screen.getByRole("button", { name: "Actions" }));
    await userEvent.click(screen.getByRole("menuitem", { name: "Archiver" }));

    expect(onSelect).toHaveBeenCalledOnce();
  });
});

describe("Tooltip", () => {
  it("s'affiche au focus clavier", async () => {
    render(
      <TooltipProvider delayDuration={0}>
        <Tooltip content="Aide contextuelle">
          <Button>Info</Button>
        </Tooltip>
      </TooltipProvider>,
    );

    await userEvent.tab();

    expect((await screen.findAllByText("Aide contextuelle")).length).toBeGreaterThan(0);
  });
});

describe("Skeleton", () => {
  it("est masqué des technologies d'assistance", () => {
    const { container } = render(<Skeleton className="h-4 w-20" />);

    expect(container.firstChild).toHaveAttribute("aria-hidden", "true");
  });
});
