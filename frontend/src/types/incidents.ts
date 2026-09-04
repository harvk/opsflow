export const INCIDENT_SEVERITIES = [
  "Low",
  "Medium",
  "High",
  "Critical",
] as const;

export type IncidentSeverity = (typeof INCIDENT_SEVERITIES)[number];

export interface IncidentDraft {
  serviceId: string;
  title: string;
  severity: IncidentSeverity;
  summary: string;
  runbookUrl: string;
}

export interface Incident extends IncidentDraft {
  id: string;
  status: "Open";
  createdAt: string;
}

export type IncidentFormErrors = Partial<Record<keyof IncidentDraft, string>>;
