import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiFetch } from "../api/apiClient";

import { getOverview, OverviewRequestError } from "./overviewClient";

import type { OverviewResponse } from "./overviewClient";

/*
 * =========================================================
 * AUTHENTICATED TRANSPORT MOCK
 * =========================================================
 *
 * The Overview client delegates transport behavior to
 * apiFetch().
 *
 * These tests must never communicate with the running
 * FastAPI application.
 */

vi.mock("../api/apiClient", () => ({
  apiFetch: vi.fn(),
}));

const apiFetchMock = vi.mocked(apiFetch);

/*
 * =========================================================
 * RESPONSE HELPERS
 * =========================================================
 */

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,

    headers: {
      "Content-Type": "application/json",
    },
  });
}

function emptyResponse(status: number): Response {
  return new Response(null, {
    status,
  });
}

/*
 * =========================================================
 * TEST DATA
 * =========================================================
 */

const overviewResponse: OverviewResponse = {
  summary: {
    totalServices: 1,

    healthyServices: 1,

    degradedServices: 0,

    criticalServices: 0,

    activeIncidents: 1,

    customerImpactingIncidents: 1,
  },

  services: [
    {
      id: "04276ddb-3d93-478d-a5cf-e1c1819c87eb",

      name: "Inventory Sync",

      owner: "Inventory",

      status: "Healthy",

      uptime: "99.87%",

      latencyMs: 115,

      description: "Inventory synchronization service.",

      region: "us-east-1",

      version: "2.8.1",

      lastDeployedAt: "2026-09-14T14:43:25.667000Z",

      dependencies: [],
    },
  ],

  incidents: [
    {
      id: "7c92da87-0416-49da-8cce-411e6648262c",

      title: "Checkout latency",

      serviceId: "04276ddb-3d93-478d-a5cf-e1c1819c87eb",

      severity: "SEV-2",

      status: "Open",

      summary: "Checkout latency is elevated.",

      assignee: "Platform Team",

      source: "monitoring",

      customerImpacting: true,

      acknowledgedAt: null,

      startedAt: "2026-09-14T14:40:00Z",

      resolvedAt: null,

      createdAt: "2026-09-14T14:41:00Z",

      updatedAt: "2026-09-14T14:42:00Z",

      reportedByEmail: "operator@example.com",
    },
  ],
  incidentDataAvailable: true,
};

const degradedOverviewResponse: OverviewResponse = {
  summary: {
    ...overviewResponse.summary,

    activeIncidents: null,

    customerImpactingIncidents: null,
  },

  services: overviewResponse.services,

  incidents: [],

  incidentDataAvailable: false,
};

/*
 * =========================================================
 * TEST LIFECYCLE
 * =========================================================
 */

beforeEach(() => {
  apiFetchMock.mockReset();
});

/*
 * =========================================================
 * COMPOSED OVERVIEW REQUEST
 * =========================================================
 */

describe("getOverview", () => {
  it("requests the composed Overview endpoint through apiFetch", async () => {
    apiFetchMock.mockResolvedValueOnce(jsonResponse(overviewResponse));

    await getOverview();

    expect(apiFetchMock).toHaveBeenCalledTimes(1);

    expect(apiFetchMock).toHaveBeenCalledWith("/overview", {
      method: "GET",

      headers: {
        Accept: "application/json",
      },
    });
  });

  it("returns the complete composed Overview response", async () => {
    apiFetchMock.mockResolvedValueOnce(jsonResponse(overviewResponse));

    const result = await getOverview();

    expect(result).toEqual(overviewResponse);

    expect(result.summary.totalServices).toBe(1);

    expect(result.summary.activeIncidents).toBe(1);

    expect(result.services[0].latencyMs).toBe(115);

    expect(result.incidents[0].severity).toBe("SEV-2");

    expect(result.incidents[0].customerImpacting).toBe(true);
  });

  it("returns an explicitly degraded successful response", async () => {
    apiFetchMock.mockResolvedValueOnce(jsonResponse(degradedOverviewResponse));

    const result = await getOverview();

    expect(result.incidentDataAvailable).toBe(false);

    expect(result.summary.activeIncidents).toBeNull();

    expect(result.summary.customerImpactingIncidents).toBeNull();

    expect(result.incidents).toEqual([]);

    expect(result.services).toEqual(overviewResponse.services);
  });

  it.each([401, 403, 500, 502, 503, 504])(
    "throws a typed request error when the endpoint returns %s",
    async (status) => {
      apiFetchMock.mockResolvedValueOnce(emptyResponse(status));

      let caughtError: unknown;

      try {
        await getOverview();
      } catch (error) {
        caughtError = error;
      }

      expect(caughtError).toBeInstanceOf(OverviewRequestError);

      expect(caughtError).toMatchObject({
        name: "OverviewRequestError",

        status,
      });
    },
  );
});
