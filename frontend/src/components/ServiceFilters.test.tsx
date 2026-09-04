import { render, screen } from "@testing-library/react";

import userEvent from "@testing-library/user-event";

import { describe, expect, it, vi } from "vitest";

import ServiceFilters from "./ServiceFilters";

describe("ServiceFilters", () => {
  it("reports search changes", async () => {
    const user = userEvent.setup();

    const handleSearch = vi.fn();

    render(
      <ServiceFilters
        searchTerm=""
        status="All"
        resultCount={4}
        onSearchTermChange={handleSearch}
        onStatusChange={vi.fn()}
        onReset={vi.fn()}
      />,
    );

    const input = screen.getByRole("searchbox", {
      name: /search services/i,
    });

    await user.type(input, "order");

    expect(handleSearch).toHaveBeenCalled();
  });
});
