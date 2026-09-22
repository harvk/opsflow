import { describe, expect, it } from "vitest";

import { enqueueWebhookNotification } from "../src/webhookHandoff";

import type { WebhookHandoffDependencies } from "../src/webhookHandoff";

import type { RealtimeIncidentMessage } from "../src/types";

function notification(): RealtimeIncidentMessage {
  return {
    type: "incident.updated",

    schema_version: "1.0",

    event_id: "7c1f9d0a-f544-47b3-b1df-642875a8fa49",

    incident_id: "aca0a505-b460-4d08-9035-3b92bac0fff1",

    task_id: "bb587a5f-3c94-4e03-8b13-159d8f58acfa",

    correlation_id: "phase-11-5g-4f4",

    status: "Investigating",

    acknowledged_at: "2026-09-22T14:00:00Z",

    occurred_at: "2026-09-22T14:00:01Z",
  };
}

describe("enqueueWebhookNotification", () => {
  it("places the exact incident.updated payload on the webhook queue", async () => {
    const sent: {
      queueUrl: string;

      body: string;
    }[] = [];

    const dependencies: WebhookHandoffDependencies = {
      queueUrl:
        "https://sqs.us-east-1.amazonaws.com/" +
        "123456789012/" +
        "opsflow-dev-webhook-notification-queue",

      sendMessage: async (queueUrl, body) => {
        sent.push({
          queueUrl,

          body,
        });
      },
    };

    const value = notification();

    await enqueueWebhookNotification(value, dependencies);

    expect(sent).toHaveLength(1);

    expect(sent[0]?.queueUrl).toBe(dependencies.queueUrl);

    expect(sent[0]?.body).toBe(JSON.stringify(value));
  });

  it("validates the public contract before queue publication", async () => {
    let sends = 0;

    const dependencies: WebhookHandoffDependencies = {
      queueUrl: "https://example.invalid/queue",

      sendMessage: async () => {
        sends += 1;
      },
    };

    const invalid = {
      ...notification(),

      correlation_id: "",
    } as RealtimeIncidentMessage;

    await expect(
      enqueueWebhookNotification(invalid, dependencies),
    ).rejects.toThrow();

    expect(sends).toBe(0);
  });

  it("propagates durable queue publication failures", async () => {
    const dependencies: WebhookHandoffDependencies = {
      queueUrl: "https://example.invalid/queue",

      sendMessage: async () => {
        throw new Error("synthetic SQS failure");
      },
    };

    await expect(
      enqueueWebhookNotification(notification(), dependencies),
    ).rejects.toThrow("synthetic SQS failure");
  });
});
