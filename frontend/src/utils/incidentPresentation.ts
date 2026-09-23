import type { IncidentApiSeverity } from "../types/incidents";

export interface IncidentSeverityPresentation {
  label: "Critical" | "High" | "Medium" | "Low";
  toneClass: string;
}

const INCIDENT_SEVERITY_PRESENTATION: Record<
  IncidentApiSeverity,
  IncidentSeverityPresentation
> = {
  "SEV-1": {
    label: "Critical",
    toneClass: "ops-severity-tone--sev-1",
  },
  "SEV-2": {
    label: "High",
    toneClass: "ops-severity-tone--sev-2",
  },
  "SEV-3": {
    label: "Medium",
    toneClass: "ops-severity-tone--sev-3",
  },
  "SEV-4": {
    label: "Low",
    toneClass: "ops-severity-tone--sev-4",
  },
};

export function getIncidentSeverityPresentation(
  severity: IncidentApiSeverity,
): IncidentSeverityPresentation {
  return INCIDENT_SEVERITY_PRESENTATION[severity];
}
