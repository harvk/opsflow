import { apiFetch } from "../api/apiClient";

import type { ServiceDetails } from "../types/dashboard";

/*
 * =========================================================
 * OVERVIEW INCIDENT READ MODEL
 * =========================================================
 *
 * This type mirrors the Backend's IncidentResponse schema.
 *
 * It intentionally remains separate from the existing
 * Incident interface in:
 *
 *   frontend/src/types/incidents.ts
 *
 * That older interface currently represents the Report
 * Incident form workflow and has a different severity and
 * lifecycle contract.
 */

export type OverviewIncidentSeverity = "SEV-1" | "SEV-2" | "SEV-3" | "SEV-4";

export type OverviewIncidentStatus =
  | "Open"
  | "Investigating"
  | "Monitoring"
  | "Resolved";

export interface OverviewIncident {
  id: string;

  title: string;

  serviceId: string;

  severity: OverviewIncidentSeverity;

  status: OverviewIncidentStatus;

  summary: string;

  assignee: string;

  source: string;

  customerImpacting: boolean;

  acknowledgedAt: string | null;

  startedAt: string;

  resolvedAt: string | null;

  createdAt: string;

  updatedAt: string;
}

/*
 * =========================================================
 * OVERVIEW SUMMARY
 * =========================================================
 */

export interface OverviewSummary {
  totalServices: number;

  healthyServices: number;

  degradedServices: number;

  criticalServices: number;

  activeIncidents: number | null;

  customerImpactingIncidents: number | null;
}

/*
 * =========================================================
 * COMPOSED OVERVIEW RESPONSE
 * =========================================================
 */

export interface OverviewResponse {
  summary: OverviewSummary;

  services: ServiceDetails[];

  incidents: OverviewIncident[];

  incidentDataAvailable: boolean;
}

/*
 * =========================================================
 * OVERVIEW REQUEST ERROR
 * =========================================================
 */

export class OverviewRequestError extends Error {
  readonly status: number;

  constructor(status: number) {
    super(`Overview request failed with status ${status}.`);

    this.name = "OverviewRequestError";

    this.status = status;
  }
}

/*
 * =========================================================
 * GET COMPOSED OVERVIEW
 * =========================================================
 *
 * apiFetch owns:
 *
 *   Bearer authentication
 *   refresh-cookie submission
 *   access-token refresh
 *   one-time request retry
 *   unauthorized event dispatch
 *
 * Because this is a GET request, no CSRF header is required.
 */

export async function getOverview(): Promise<OverviewResponse> {
  const response = await apiFetch("/overview", {
    method: "GET",

    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new OverviewRequestError(response.status);
  }

  return response.json() as Promise<OverviewResponse>;
}
