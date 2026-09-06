import { render, screen } from "@testing-library/react";

import userEvent from "@testing-library/user-event";

import { MemoryRouter } from "react-router-dom";

import { describe, expect, it, vi } from "vitest";

import ReportIncidentPage from "./ReportIncidentPage";

vi.mock("../hooks/useServices", () => ({
  useServices: () => ({
    retry: vi.fn(),

    requestState: {
      status: "success",

      error: null,

      data: [
        {
          id: "order-api",
          name: "Order API",
          owner: "Fulfillment",
          status: "Healthy",
          uptime: "99.99%",
          latencyMs: 118,
        },
      ],
    },
  }),
}));

describe("ReportIncidentPage", () => {
  it("shows validation errors for missing incident details", async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <ReportIncidentPage />
      </MemoryRouter>,
    );

    await user.click(
      screen.getByRole("button", {
        name: /create incident/i,
      }),
    );

    expect(await screen.findByText(/select a service/i)).toBeInTheDocument();

    expect(screen.getByText(/enter an incident title/i)).toBeInTheDocument();

    expect(screen.getByText(/describe the incident/i)).toBeInTheDocument();
  });
});
