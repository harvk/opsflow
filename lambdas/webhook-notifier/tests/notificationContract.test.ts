import { describe, expect, it } from "vitest";

import {
  InvalidWebhookNotificationError,
  validateWebhookNotification,
} from "../src/notificationContract";

function validNotification(): Record<string, unknown> {
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

describe("webhook notification contract", () => {
  it("accepts incident.updated v1", () => {
    const notification = validateWebhookNotification(validNotification());

    expect(notification.type).toBe("incident.updated");

    expect(notification.schema_version).toBe("1.0");
  });

  it("accepts a non-UUID correlation identifier", () => {
    const notification = {
      ...validNotification(),

      correlation_id: "phase-11-5g-4f-webhook",
    };

    expect(validateWebhookNotification(notification).correlation_id).toBe(
      "phase-11-5g-4f-webhook",
    );
  });

  it("rejects an empty correlation identifier", () => {
    const notification = {
      ...validNotification(),

      correlation_id: "",
    };

    expect(() => validateWebhookNotification(notification)).toThrow(
      InvalidWebhookNotificationError,
    );
  });

  it("rejects the wrong notification type", () => {
    const notification = {
      ...validNotification(),

      type: "incident.created",
    };

    expect(() => validateWebhookNotification(notification)).toThrow(
      InvalidWebhookNotificationError,
    );
  });

  it("rejects unsupported schema versions", () => {
    const notification = {
      ...validNotification(),

      schema_version: "2.0",
    };

    expect(() => validateWebhookNotification(notification)).toThrow(
      InvalidWebhookNotificationError,
    );
  });

  it("rejects additional properties", () => {
    const notification = {
      ...validNotification(),

      unexpected: true,
    };

    expect(() => validateWebhookNotification(notification)).toThrow(
      InvalidWebhookNotificationError,
    );
  });
});
