import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import ServiceIncidentHistory from "./ServiceIncidentHistory";

import type { Incident } from "../types/incidents";

const INCIDENTS: Incident[] = [
  {
    id: "1",
    title: "Newest incident",
    serviceId: "service-1",
    severity: "SEV-4",
    status: "Open",
    summary: "Newest incident summary.",
    assignee: "Platform",
    source: "seed",
    customerImpacting: false,
    acknowledgedAt: null,
    startedAt: "2026-09-23T14:00:00Z",
    resolvedAt: null,
    createdAt: "2026-09-23T14:05:00Z",
    updatedAt: "2026-09-23T14:05:00Z",
    reportedByEmail: "admin@example.com",
  },
  {
    id: "2",
    title: "Older incident",
    serviceId: "service-1",
    severity: "SEV-1",
    status: "Resolved",
    summary: "Older incident summary.",
    assignee: "Reliability",
    source: "seed",
    customerImpacting: true,
    acknowledgedAt: "2026-09-22T12:10:00Z",
    startedAt: "2026-09-22T12:00:00Z",
    resolvedAt: "2026-09-22T13:00:00Z",
    createdAt: "2026-09-22T12:05:00Z",
    updatedAt: "2026-09-22T13:00:00Z",
    reportedByEmail: null,
  },
];

describe("ServiceIncidentHistory", () => {
  it("renders all incidents with mapped severity labels and provenance", () => {
    const { container } = render(
      <ServiceIncidentHistory incidents={INCIDENTS} />,
    );

    expect(screen.getByText("2 reported")).toBeInTheDocument();
    expect(screen.getByText("Newest incident")).toBeInTheDocument();
    expect(screen.getByText("Older incident")).toBeInTheDocument();
    expect(screen.getByText("Low")).toBeInTheDocument();
    expect(screen.getByText("Critical")).toBeInTheDocument();
    expect(screen.getByText("admin@example.com")).toBeInTheDocument();
    expect(screen.getByText("Legacy / system record")).toBeInTheDocument();
    expect(screen.getByText("Customer impacting")).toBeInTheDocument();

    expect(
      container.querySelector(".ops-severity-tone--sev-1"),
    ).not.toBeNull();
    expect(
      container.querySelector(".ops-severity-tone--sev-4"),
    ).not.toBeNull();

    const resolvedStatus = screen.getByText("Resolved");
    expect(resolvedStatus).toHaveClass(
      "ops-service-incident__status--resolved",
    );
  });

  it("renders an empty state when the service has no incidents", () => {
    render(<ServiceIncidentHistory incidents={[]} />);

    expect(
      screen.getByText("No incidents have been reported for this service."),
    ).toBeInTheDocument();
  });
});
