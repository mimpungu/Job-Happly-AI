import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Pagination, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./table";

describe("Table", () => {
  it("expose les en-têtes de colonnes et les cellules", () => {
    render(
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Poste</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell>Data Analyst</TableCell>
          </TableRow>
        </TableBody>
      </Table>,
    );

    expect(screen.getByRole("columnheader", { name: "Poste" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Data Analyst" })).toBeInTheDocument();
  });
});

describe("Pagination", () => {
  it("navigue vers la page suivante et précédente", async () => {
    const onPageChange = vi.fn();
    render(<Pagination page={2} pageCount={3} onPageChange={onPageChange} />);

    await userEvent.click(screen.getByRole("button", { name: /Suivant/ }));
    await userEvent.click(screen.getByRole("button", { name: /Précédent/ }));

    expect(onPageChange).toHaveBeenNthCalledWith(1, 3);
    expect(onPageChange).toHaveBeenNthCalledWith(2, 1);
  });

  it("désactive les bornes", () => {
    const { rerender } = render(<Pagination page={1} pageCount={3} onPageChange={() => {}} />);
    expect(screen.getByRole("button", { name: /Précédent/ })).toBeDisabled();

    rerender(<Pagination page={3} pageCount={3} onPageChange={() => {}} />);
    expect(screen.getByRole("button", { name: /Suivant/ })).toBeDisabled();
  });

  it("reste cohérente avec zéro page ou une page hors bornes", () => {
    render(<Pagination page={9} pageCount={0} onPageChange={() => {}} />);

    expect(screen.getByText("Page 1 sur 1")).toBeInTheDocument();
  });
});
