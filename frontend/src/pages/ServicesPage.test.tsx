import { render, screen } from "@testing-library/react";

import { MemoryRouter } from "react-router";

import { beforeEach, describe, expect, it, vi } from "vitest";

import ServicesPage from "./ServicesPage";

import { getServices } from "../services/serviceClient";

vi.mock("../services/serviceClient", () => ({
  getServices: vi.fn(),
}));

const mockedGetServices = vi.mocked(getServices);

describe("ServicesPage", () => {
  beforeEach(() => {
    mockedGetServices.mockResolvedValue([
      {
        id: "order-api",
        name: "Order API",
        owner: "Fulfillment",
        status: "Healthy",
        uptime: "99.99%",
        latencyMs: 118,
      },
      {
        id: "payment-webhook",
        name: "Payment Webhook",
        owner: "Payments",
        status: "Critical",
        uptime: "98.91%",
        latencyMs: 621,
      },
    ]);
  });

  it("applies filters from the URL", async () => {
    render(
      <MemoryRouter initialEntries={["/services?q=order&status=Healthy"]}>
        <ServicesPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Order API")).toBeInTheDocument();

    expect(screen.queryByText("Payment Webhook")).not.toBeInTheDocument();
  });
});
