import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import Ajv2020, {
  type AnySchema,
  type ErrorObject,
  type ValidateFunction,
} from "ajv/dist/2020.js";

import addFormats from "ajv-formats";

import { describe, expect, it } from "vitest";

import { buildRealtimeIncidentMessage } from "../src/notifier";

import type {
  IncidentTaskCompletedEvent,
  RealtimeIncidentMessage,
} from "../src/types";

const schemaPath = resolve(
  process.cwd(),
  "../../contracts/notifications/incident-updated-v1.schema.json",
);

const fixturePath = resolve(
  process.cwd(),
  "../../contracts/notifications/examples/valid-incident-updated-v1.json",
);

const schema = JSON.parse(readFileSync(schemaPath, "utf8")) as AnySchema;

const fixture = JSON.parse(readFileSync(fixturePath, "utf8")) as unknown;

const ajv = new Ajv2020({
  allErrors: true,
  strict: true,
});

addFormats(ajv);

const validate = ajv.compile(schema) as ValidateFunction<unknown>;

function validationErrors(): ErrorObject[] {
  return validate.errors ? [...validate.errors] : [];
}

function completedEvent(): IncidentTaskCompletedEvent {
  return {
    schema_version: "1.0",

    event_type: "incident.task.completed",

    event_id: "7c1f9d0a-f544-47b3-b1df-642875a8fa49",

    incident_id: "aca0a505-b460-4d08-9035-3b92bac0fff1",

    task_id: "bb587a5f-3c94-4e03-8b13-159d8f58acfa",

    correlation_id: "7385b223-c727-4297-ade2-d8089fa2d9c2",

    status: "Investigating",

    acknowledged_at: "2026-09-21T16:00:00Z",

    occurred_at: "2026-09-21T16:00:01Z",
  };
}

function expectValidNotification(value: unknown): void {
  const valid = validate(value);

  expect(validationErrors()).toEqual([]);

  expect(valid).toBe(true);
}

function expectInvalidNotification(value: unknown): void {
  const valid = validate(value);

  expect(valid).toBe(false);

  expect(validationErrors().length).toBeGreaterThan(0);
}

describe("incident.updated v1 notification contract", () => {
  it("accepts the canonical contract fixture", () => {
    expectValidNotification(fixture);
  });

  it("accepts the realtime notifier output", () => {
    const message = buildRealtimeIncidentMessage(completedEvent());

    expectValidNotification(message);
  });

  it("preserves the expected correlation identities", () => {
    const event = completedEvent();

    const message = buildRealtimeIncidentMessage(event);

    expect(message.event_id).toBe(event.event_id);

    expect(message.incident_id).toBe(event.incident_id);

    expect(message.task_id).toBe(event.task_id);

    expect(message.correlation_id).toBe(event.correlation_id);
  });

  it("allows a null acknowledgement timestamp", () => {
    const event = {
      ...completedEvent(),

      acknowledged_at: null,
    };

    const message = buildRealtimeIncidentMessage(event);

    expectValidNotification(message);
  });

  it("rejects an unsupported notification type", () => {
    const invalid = {
      ...(fixture as RealtimeIncidentMessage),

      type: "incident.created",
    };

    expectInvalidNotification(invalid);
  });

  it("rejects an unsupported schema version", () => {
    const invalid = {
      ...(fixture as RealtimeIncidentMessage),

      schema_version: "2.0",
    };

    expectInvalidNotification(invalid);
  });

  it("rejects an unsupported incident status", () => {
    const invalid = {
      ...(fixture as RealtimeIncidentMessage),

      status: "Deleted",
    };

    expectInvalidNotification(invalid);
  });

  it("rejects malformed correlation identifiers", () => {
    const invalid = {
      ...(fixture as RealtimeIncidentMessage),

      correlation_id: "not-a-uuid",
    };

    expectInvalidNotification(invalid);
  });

  it("rejects additional undeclared properties", () => {
    const invalid = {
      ...(fixture as RealtimeIncidentMessage),

      unexpected_field: true,
    };

    expectInvalidNotification(invalid);
  });

  it("rejects a missing required event identifier", () => {
    const { event_id: _eventId, ...invalid } =
      fixture as RealtimeIncidentMessage;

    expectInvalidNotification(invalid);
  });
});
