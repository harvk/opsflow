import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import ServiceHealthSummary from "./ServiceHealthSummary";

import type { Service } from "../types/dashboard";

const SERVICES: Service[] = [
  {
    id: "healthy-1",
    name: "Healthy service",
    owner: "Platform",
    status: "Healthy",
    uptime: "99.99%",
    latencyMs: 20,
  },
  {
    id: "degraded-1",
    name: "Degraded service",
    owner: "Platform",
    status: "Degraded",
    uptime: "99.5%",
    latencyMs: 140,
  },
  {
    id: "critical-1",
    name: "Critical service",
    owner: "Platform",
    status: "Critical",
    uptime: "97.5%",
    latencyMs: 600,
  },
];

describe("ServiceHealthSummary", () => {
  it("renders color-coordinated status rows with their counts", () => {
    const { container } = render(
      <MemoryRouter>
        <ServiceHealthSummary services={SERVICES} />
      </MemoryRouter>,
    );

    expect(screen.getByText("Healthy")).toBeInTheDocument();
    expect(screen.getByText("Degraded")).toBeInTheDocument();
    expect(screen.getByText("Critical")).toBeInTheDocument();

    expect(container.querySelector(".ops-health-status--healthy")).not.toBeNull();
    expect(container.querySelector(".ops-health-status--degraded")).not.toBeNull();
    expect(container.querySelector(".ops-health-status--critical")).not.toBeNull();
  });
});
