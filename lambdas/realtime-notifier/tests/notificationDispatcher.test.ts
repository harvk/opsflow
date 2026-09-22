import { describe, expect, it } from "vitest";

import {
  NotificationDispatchError,
  dispatchIncidentTaskCompletedEvent,
} from "../src/notificationDispatcher";

import type { NotificationDispatcherDependencies } from "../src/notificationDispatcher";

import type {
  IncidentTaskCompletedEvent,
  RealtimeIncidentMessage,
} from "../src/types";

function completedEvent(): IncidentTaskCompletedEvent {
  return {
    schema_version: "1.0",

    event_type: "incident.task.completed",

    event_id: "7c1f9d0a-f544-47b3-b1df-642875a8fa49",

    incident_id: "aca0a505-b460-4d08-9035-3b92bac0fff1",

    task_id: "bb587a5f-3c94-4e03-8b13-159d8f58acfa",

    correlation_id: "phase-11-5g-4f4",

    status: "Investigating",

    acknowledged_at: "2026-09-22T14:00:00Z",

    occurred_at: "2026-09-22T14:00:01Z",
  };
}

describe("dispatchIncidentTaskCompletedEvent", () => {
  it("attempts both WebSocket delivery and webhook handoff", async () => {
    const websocketEvents: IncidentTaskCompletedEvent[] = [];

    const webhookEvents: RealtimeIncidentMessage[] = [];

    const dependencies: NotificationDispatcherDependencies = {
      broadcastNotification: async (event) => {
        websocketEvents.push(event);
      },

      enqueueWebhookNotification: async (notification) => {
        webhookEvents.push(notification);
      },
    };

    const event = completedEvent();

    await dispatchIncidentTaskCompletedEvent(event, dependencies);

    expect(websocketEvents).toEqual([event]);

    expect(webhookEvents).toEqual([
      {
        type: "incident.updated",

        schema_version: "1.0",

        event_id: event.event_id,

        incident_id: event.incident_id,

        task_id: event.task_id,

        correlation_id: event.correlation_id,

        status: event.status,

        acknowledged_at: event.acknowledged_at,

        occurred_at: event.occurred_at,
      },
    ]);
  });

  it("still attempts the webhook handoff when WebSocket delivery fails", async () => {
    let webhookAttempts = 0;

    const dependencies: NotificationDispatcherDependencies = {
      broadcastNotification: async () => {
        throw new Error("synthetic WebSocket failure");
      },

      enqueueWebhookNotification: async () => {
        webhookAttempts += 1;
      },
    };

    await expect(
      dispatchIncidentTaskCompletedEvent(completedEvent(), dependencies),
    ).rejects.toMatchObject({
      name: "NotificationDispatchError",

      failures: [
        {
          channel: "websocket",

          errorType: "Error",

          message: "synthetic WebSocket failure",
        },
      ],
    });

    expect(webhookAttempts).toBe(1);
  });

  it("still attempts WebSocket delivery when webhook handoff fails", async () => {
    let websocketAttempts = 0;

    const dependencies: NotificationDispatcherDependencies = {
      broadcastNotification: async () => {
        websocketAttempts += 1;
      },

      enqueueWebhookNotification: async () => {
        throw new Error("synthetic webhook queue failure");
      },
    };

    await expect(
      dispatchIncidentTaskCompletedEvent(completedEvent(), dependencies),
    ).rejects.toMatchObject({
      name: "NotificationDispatchError",

      failures: [
        {
          channel: "webhook",

          errorType: "Error",

          message: "synthetic webhook queue failure",
        },
      ],
    });

    expect(websocketAttempts).toBe(1);
  });

  it("aggregates failures from both paths", async () => {
    const dependencies: NotificationDispatcherDependencies = {
      broadcastNotification: async () => {
        throw new Error("websocket failed");
      },

      enqueueWebhookNotification: async () => {
        throw new Error("webhook failed");
      },
    };

    try {
      await dispatchIncidentTaskCompletedEvent(completedEvent(), dependencies);

      throw new Error("Expected dispatch failure.");
    } catch (error) {
      expect(error).toBeInstanceOf(NotificationDispatchError);

      if (!(error instanceof NotificationDispatchError)) {
        throw error;
      }

      expect(error.eventId).toBe("7c1f9d0a-f544-47b3-b1df-642875a8fa49");

      expect(error.failures).toEqual([
        {
          channel: "websocket",

          errorType: "Error",

          message: "websocket failed",
        },

        {
          channel: "webhook",

          errorType: "Error",

          message: "webhook failed",
        },
      ]);
    }
  });
});
