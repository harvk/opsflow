export type IncidentStatus =
  | "Open"
  | "Investigating"
  | "Monitoring"
  | "Resolved";

export interface IncidentUpdatedNotification {
  type: "incident.updated";

  schema_version: "1.0";

  event_id: string;

  incident_id: string;

  task_id: string;

  correlation_id: string;

  status: IncidentStatus;

  acknowledged_at: string | null;

  occurred_at: string;
}

export interface WebhookDeliveryTarget {
  url: string;
}

export interface WebhookHttpRequest {
  method: "POST";

  url: string;

  headers: Readonly<Record<string, string>>;

  body: string;
}
