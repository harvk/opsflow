import { render, screen } from "@testing-library/react";

import { MemoryRouter, Route, Routes } from "react-router-dom";

import { describe, expect, it, vi } from "vitest";

import ServiceDetailsPage from "./ServiceDetailsPage";

vi.mock("../hooks/useServiceDetails", () => ({
  useServiceDetails: () => ({
    status: "success",
    error: null,
    data: {
      id: "order-api",
      name: "Order API",
      owner: "Fulfillment",
      status: "Healthy",
      uptime: "99.99%",
      latencyMs: 118,
      description: "Processes orders.",
      region: "us-east-1",
      version: "2.8.1",
      lastDeployedAt: "2026-09-04T13:42:00Z",
      dependencies: [],
    },
  }),
}));

describe("ServiceDetailsPage", () => {
  it("renders service details for a dynamic route", () => {
    render(
      <MemoryRouter initialEntries={["/services/order-api"]}>
        <Routes>
          <Route path="/services/:serviceId" element={<ServiceDetailsPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("heading", {
        name: /order api/i,
      }),
    ).toBeInTheDocument();

    expect(screen.getByText(/us-east-1/i)).toBeInTheDocument();

    expect(
      screen.getByRole("link", {
        name: /report incident/i,
      }),
    ).toBeInTheDocument();
  });
});
