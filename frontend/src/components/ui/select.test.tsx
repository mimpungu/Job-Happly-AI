import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Select } from "./select";

const options = [
  { value: "cdi", label: "CDI" },
  { value: "cdd", label: "CDD" },
];

describe("Select", () => {
  it("liste les options et le placeholder", () => {
    render(<Select aria-label="Contrat" options={options} placeholder="Tous" />);

    expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual(["Tous", "CDI", "CDD"]);
  });

  it("notifie le changement de valeur", async () => {
    const onChange = vi.fn();
    render(<Select aria-label="Contrat" options={options} onChange={onChange} />);

    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Contrat" }), "cdd");

    expect(screen.getByRole("combobox")).toHaveValue("cdd");
    expect(onChange).toHaveBeenCalledOnce();
  });
});
