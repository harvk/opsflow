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

vi.mock("../hooks/useServiceIncidents", () => ({
  useServiceIncidents: () => ({
    status: "success",
    error: null,
    data: [
      {
        id: "90b0df11-af28-4697-a97f-0926cf703676",
        title: "Order submission latency",
        serviceId: "order-api",
        severity: "SEV-2",
        status: "Investigating",
        summary: "Order submissions are taking longer than expected.",
        assignee: "Fulfillment Team",
        source: "seed",
        customerImpacting: true,
        acknowledgedAt: "2026-09-23T12:10:00Z",
        startedAt: "2026-09-23T12:00:00Z",
        resolvedAt: null,
        createdAt: "2026-09-23T12:05:00Z",
        updatedAt: "2026-09-23T12:20:00Z",
        reportedByEmail: "admin@example.com",
      },
    ],
  }),
}));

describe("ServiceDetailsPage", () => {
  it("renders service details and every incident associated with the service", () => {
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

    expect(
      screen.getByRole("heading", {
        name: /reported incidents/i,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("Order submission latency")).toBeInTheDocument();
    expect(screen.getByText("High")).toBeInTheDocument();
    expect(screen.getByText("admin@example.com")).toBeInTheDocument();
    expect(screen.getByText("Customer impacting")).toBeInTheDocument();

    const statusFactCards = document.querySelectorAll(
      ".ops-service-fact-card--healthy",
    );
    expect(statusFactCards).toHaveLength(4);
  });
});
