export const INCIDENT_STATUSES = [
  "Open",
  "Investigating",
  "Monitoring",
  "Resolved",
] as const;

export type IncidentStatus = (typeof INCIDENT_STATUSES)[number];

export interface IncidentTaskCompletedEvent {
  schema_version: "1.0";

  event_type: "incident.task.completed";

  event_id: string;

  incident_id: string;

  task_id: string;

  correlation_id: string;

  status: IncidentStatus;

  acknowledged_at: string | null;

  occurred_at: string;
}

export interface ConnectionRecord {
  channel: string;

  connection_id: string;

  domain_name: string;

  stage: string;

  connected_at: string;

  expires_at: number;
}

export interface SaveConnectionInput {
  connectionId: string;

  domainName: string;

  stage: string;
}

export interface RealtimeIncidentMessage {
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

export interface WebSocketResponse {
  statusCode: number;

  body?: string;
}

export interface SqsBatchFailure {
  itemIdentifier: string;
}

export interface SqsBatchResponse {
  batchItemFailures: SqsBatchFailure[];
}
