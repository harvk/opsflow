import {
  INCIDENT_STATUSES,
  type IncidentStatus,
  type IncidentTaskCompletedEvent,
} from "./types";

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export class InvalidNotificationError extends Error {
  constructor(message: string) {
    super(message);

    this.name = "InvalidNotificationError";
  }
}

function requireObject(value: unknown): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new InvalidNotificationError("Notification must be a JSON object");
  }

  return value as Record<string, unknown>;
}

function requireString(value: unknown, field: string): string {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new InvalidNotificationError(`${field} must be a non-empty string`);
  }

  return value;
}

function requireUuid(value: unknown, field: string): string {
  const resolved = requireString(value, field);

  if (!UUID_PATTERN.test(resolved)) {
    throw new InvalidNotificationError(`${field} must be a UUID`);
  }

  return resolved;
}

function requireDateTime(value: unknown, field: string): string {
  const resolved = requireString(value, field);

  if (Number.isNaN(Date.parse(resolved))) {
    throw new InvalidNotificationError(
      `${field} must be an ISO-8601 date-time`,
    );
  }

  return resolved;
}

function requireNullableDateTime(value: unknown, field: string): string | null {
  if (value === null) {
    return null;
  }

  return requireDateTime(value, field);
}

function requireIncidentStatus(value: unknown): IncidentStatus {
  const resolved = requireString(value, "status");

  if (!INCIDENT_STATUSES.includes(resolved as IncidentStatus)) {
    throw new InvalidNotificationError(
      `status must be one of: ${INCIDENT_STATUSES.join(", ")}`,
    );
  }

  return resolved as IncidentStatus;
}

export function parseIncidentTaskCompletedEvent(
  body: string,
): IncidentTaskCompletedEvent {
  let candidate: unknown;

  try {
    candidate = JSON.parse(body);
  } catch {
    throw new InvalidNotificationError(
      "Notification body must contain valid JSON",
    );
  }

  const event = requireObject(candidate);

  if (event.schema_version !== "1.0") {
    throw new InvalidNotificationError("schema_version must equal 1.0");
  }

  if (event.event_type !== "incident.task.completed") {
    throw new InvalidNotificationError(
      "event_type must equal incident.task.completed",
    );
  }

  return {
    schema_version: "1.0",

    event_type: "incident.task.completed",

    event_id: requireUuid(event.event_id, "event_id"),

    incident_id: requireUuid(event.incident_id, "incident_id"),

    task_id: requireUuid(event.task_id, "task_id"),

    correlation_id: requireString(event.correlation_id, "correlation_id"),

    status: requireIncidentStatus(event.status),

    acknowledged_at: requireNullableDateTime(
      event.acknowledged_at,
      "acknowledged_at",
    ),

    occurred_at: requireDateTime(event.occurred_at, "occurred_at"),
  };
}
