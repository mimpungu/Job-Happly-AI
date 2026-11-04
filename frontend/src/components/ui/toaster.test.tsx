import { act, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { toast, Toaster } from "./toaster";

describe("Toaster", () => {
  it("affiche une notification déclenchée par toast()", async () => {
    render(<Toaster />);

    act(() => {
      toast("Recherche enregistrée");
    });

    expect(await screen.findByText("Recherche enregistrée")).toBeInTheDocument();
  });
});
