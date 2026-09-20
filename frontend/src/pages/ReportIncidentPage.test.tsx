import { render, screen } from "@testing-library/react";

import userEvent from "@testing-library/user-event";

import { MemoryRouter } from "react-router-dom";

import { beforeEach, describe, expect, it, vi } from "vitest";

import ReportIncidentPage from "./ReportIncidentPage";

import { createIncident } from "../services/serviceClient";

vi.mock("../hooks/useServices", () => ({
  useServices: () => ({
    retry: vi.fn(),

    requestState: {
      status: "success",

      error: null,

      data: [
        {
          id: "604ee093-cafc-42a9-b224-d91d6c1f5680",

          name: "Identity",

          owner: "Platform Team",

          status: "Degraded",

          uptime: "97.94%",

          latencyMs: 120,
        },
      ],
    },
  }),
}));

vi.mock("../services/serviceClient", () => ({
  createIncident: vi.fn(),
}));

const mockedCreateIncident = vi.mocked(createIncident);

describe("ReportIncidentPage", () => {
  beforeEach(() => {
    mockedCreateIncident.mockReset();
  });

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

    expect(mockedCreateIncident).not.toHaveBeenCalled();
  });
});
