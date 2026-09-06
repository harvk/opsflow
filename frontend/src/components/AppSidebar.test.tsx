import { render, screen } from "@testing-library/react";

import { MemoryRouter } from "react-router-dom";

import { describe, expect, it, vi } from "vitest";

import AppSidebar from "./AppSidebar";

describe("AppSidebar", () => {
  it("renders primary navigation links", () => {
    render(
      <MemoryRouter>
        <AppSidebar isOpen onClose={vi.fn()} />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("link", {
        name: /overview/i,
      }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("link", {
        name: /services/i,
      }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("link", {
        name: /report incident/i,
      }),
    ).toBeInTheDocument();
  });
});
