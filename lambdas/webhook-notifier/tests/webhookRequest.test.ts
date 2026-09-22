import { describe, expect, it } from "vitest";

import {
  InvalidWebhookTargetError,
  buildWebhookRequest,
} from "../src/webhookRequest";

import type { IncidentUpdatedNotification } from "../src/types";

function notification(): IncidentUpdatedNotification {
  return {
    type: "incident.updated",

    schema_version: "1.0",

    event_id: "7c1f9d0a-f544-47b3-b1df-642875a8fa49",

    incident_id: "aca0a505-b460-4d08-9035-3b92bac0fff1",

    task_id: "bb587a5f-3c94-4e03-8b13-159d8f58acfa",

    correlation_id: "phase-11-5g-4f1",

    status: "Investigating",

    acknowledged_at: "2026-09-22T14:00:00Z",

    occurred_at: "2026-09-22T14:00:01Z",
  };
}

describe("buildWebhookRequest", () => {
  it("creates an HTTPS POST request", () => {
    const value = notification();

    const request = buildWebhookRequest(value, {
      url: "https://example.com/hooks/incidents",
    });

    expect(request.method).toBe("POST");

    expect(request.url).toBe("https://example.com/hooks/incidents");

    expect(JSON.parse(request.body)).toEqual(value);
  });

  it("includes stable notification identity headers", () => {
    const value = notification();

    const request = buildWebhookRequest(value, {
      url: "https://example.com/hooks/incidents",
    });

    expect(request.headers["content-type"]).toBe("application/json");

    expect(request.headers["user-agent"]).toBe("OpsFlow-Webhook/1.0");

    expect(request.headers["x-opsflow-event-id"]).toBe(value.event_id);

    expect(request.headers["x-opsflow-event-type"]).toBe("incident.updated");

    expect(request.headers["x-opsflow-schema-version"]).toBe("1.0");
  });

  it("rejects non-HTTPS targets", () => {
    expect(() =>
      buildWebhookRequest(notification(), {
        url: "http://example.com/hooks/incidents",
      }),
    ).toThrow(InvalidWebhookTargetError);
  });

  it("rejects embedded URL credentials", () => {
    expect(() =>
      buildWebhookRequest(notification(), {
        url: "https://user:secret@example.com/hooks",
      }),
    ).toThrow(InvalidWebhookTargetError);
  });

  it("rejects invalid absolute URLs", () => {
    expect(() =>
      buildWebhookRequest(notification(), {
        url: "not-a-url",
      }),
    ).toThrow(InvalidWebhookTargetError);
  });

  it("does not mutate the source notification", () => {
    const value = notification();

    const before = JSON.stringify(value);

    buildWebhookRequest(value, {
      url: "https://example.com/hooks/incidents",
    });

    expect(JSON.stringify(value)).toBe(before);
  });
});
