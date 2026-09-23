import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiFetch } from "../api/apiClient";

import { getServiceIncidents } from "./serviceClient";

import type { Incident } from "../types/incidents";

vi.mock("../api/apiClient", () => ({
  apiFetch: vi.fn(),
}));

const apiFetchMock = vi.mocked(apiFetch);

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

function incident(id: string): Incident {
  return {
    id,
    title: `Incident ${id}`,
    serviceId: "service-1",
    severity: "SEV-2",
    status: "Open",
    summary: "Incident summary.",
    assignee: "Platform",
    source: "test",
    customerImpacting: false,
    acknowledgedAt: null,
    startedAt: "2026-09-23T12:00:00Z",
    resolvedAt: null,
    createdAt: "2026-09-23T12:05:00Z",
    updatedAt: "2026-09-23T12:05:00Z",
    reportedByEmail: "admin@example.com",
  };
}

beforeEach(() => {
  apiFetchMock.mockReset();
});

describe("getServiceIncidents", () => {
  it("requests the service-scoped incident endpoint", async () => {
    apiFetchMock.mockResolvedValueOnce(jsonResponse([incident("1")]));

    const result = await getServiceIncidents("service-1");

    expect(result).toHaveLength(1);
    expect(apiFetchMock).toHaveBeenCalledWith(
      "/services/service-1/incidents?offset=0&limit=100",
      {
        method: "GET",
        headers: expect.any(Headers),
      },
    );
  });

  it("continues requesting pages until every incident is returned", async () => {
    const firstPage = Array.from({ length: 100 }, (_, index) =>
      incident(String(index + 1)),
    );
    const secondPage = [incident("101"), incident("102")];

    apiFetchMock
      .mockResolvedValueOnce(jsonResponse(firstPage))
      .mockResolvedValueOnce(jsonResponse(secondPage));

    const result = await getServiceIncidents("service-1");

    expect(result).toHaveLength(102);
    expect(apiFetchMock).toHaveBeenCalledTimes(2);
    expect(apiFetchMock.mock.calls[1][0]).toBe(
      "/services/service-1/incidents?offset=100&limit=100",
    );
  });
});
