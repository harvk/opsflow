export const INCIDENT_SEVERITIES = [
  "Low",
  "Medium",
  "High",
  "Critical",
] as const;

export type IncidentFormSeverity = (typeof INCIDENT_SEVERITIES)[number];

export type IncidentApiSeverity = "SEV-1" | "SEV-2" | "SEV-3" | "SEV-4";

export type IncidentStatus =
  | "Open"
  | "Investigating"
  | "Monitoring"
  | "Resolved";

/*
 * =========================================================
 * REPORT INCIDENT FORM
 * =========================================================
 *
 * This represents what the browser form edits.
 *
 * Severity labels remain human-friendly and are translated
 * to the Incident Service severity contract at the API
 * boundary.
 *
 * runbookUrl remains form-only data because the current
 * Incident Service IncidentCreate schema does not persist
 * a runbook URL.
 */

export interface IncidentDraft {
  serviceId: string;

  title: string;

  severity: IncidentFormSeverity;

  summary: string;

  assignee: string;

  runbookUrl: string;
}

/*
 * =========================================================
 * INCIDENT CREATE API CONTRACT
 * =========================================================
 *
 * This is the payload sent to POST /incidents.
 *
 * It deliberately excludes runbookUrl.
 */

export interface IncidentCreateRequest {
  serviceId: string;

  title: string;

  severity: IncidentApiSeverity;

  summary: string;

  assignee: string;
}

/*
 * =========================================================
 * INCIDENT API RESPONSE
 * =========================================================
 *
 * Mirrors the Incident Service IncidentResponse schema.
 */

export interface Incident {
  id: string;

  title: string;

  serviceId: string;

  severity: IncidentApiSeverity;

  status: IncidentStatus;

  summary: string;

  assignee: string;

  source: string;

  customerImpacting: boolean;

  acknowledgedAt: string | null;

  startedAt: string;

  resolvedAt: string | null;

  createdAt: string;

  updatedAt: string;

  reportedByEmail: string | null;
}

export type IncidentFormErrors = Partial<Record<keyof IncidentDraft, string>>;
