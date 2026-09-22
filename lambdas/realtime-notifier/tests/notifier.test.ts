import { describe, expect, it, vi } from "vitest";

import {
  broadcastIncidentTaskCompletedEvent,
  RealtimeFanoutDeliveryError,
  type BroadcastDependencies,
} from "../src/notifier";

import type {
  ConnectionRecord,
  IncidentTaskCompletedEvent,
} from "../src/types";

const INCIDENTS_CHANNEL = "incidents";

function notification(): IncidentTaskCompletedEvent {
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

function connection(
  connectionId: string,
  channel: string = INCIDENTS_CHANNEL,
): ConnectionRecord {
  return {
    channel,

    connection_id: connectionId,

    domain_name: "abc123.execute-api.us-east-1.amazonaws.com",

    stage: "dev",

    connected_at: "2026-09-21T16:00:00Z",

    expires_at: 1790000000,
  };
}

function baseDependencies(
  overrides: Partial<BroadcastDependencies> = {},
): BroadcastDependencies {
  return {
    targetChannel: INCIDENTS_CHANNEL,

    listConnections: async () => [],

    deleteConnection: async () => {},

    postToConnection: async () => {},

    ...overrides,
  };
}

describe("broadcastIncidentTaskCompletedEvent", () => {
  it("delivers the incident update to every active connection in the target channel", async () => {
    const sent: {
      connectionId: string;
      payload: string;
    }[] = [];

    const dependencies = baseDependencies({
      listConnections: async () => [
        connection("connection-a"),

        connection("connection-b"),
      ],

      postToConnection: async (target, payload) => {
        sent.push({
          connectionId: target.connection_id,

          payload,
        });
      },
    });

    await broadcastIncidentTaskCompletedEvent(notification(), dependencies);

    expect(sent.map((entry) => entry.connectionId)).toEqual([
      "connection-a",
      "connection-b",
    ]);

    const payload = JSON.parse(sent[0]?.payload ?? "{}");

    expect(payload.type).toBe("incident.updated");

    expect(payload.incident_id).toBe("aca0a505-b460-4d08-9035-3b92bac0fff1");

    expect(payload.status).toBe("Investigating");
  });

  it("skips connections belonging to a different channel", async () => {
    const delivered: string[] = [];

    const consoleWarn = vi.spyOn(console, "warn").mockImplementation(() => {});

    const dependencies = baseDependencies({
      listConnections: async () => [
        connection("incident-client", "incidents"),

        connection("audit-client", "audit"),
      ],

      postToConnection: async (target) => {
        delivered.push(target.connection_id);
      },
    });

    try {
      await broadcastIncidentTaskCompletedEvent(notification(), dependencies);

      expect(delivered).toEqual(["incident-client"]);

      expect(consoleWarn).toHaveBeenCalledTimes(1);

      const rawLog = consoleWarn.mock.calls[0]?.[0];

      const log = JSON.parse(String(rawLog));

      expect(log).toMatchObject({
        level: "warning",

        event: "websocket_cross_channel_connection_skipped",

        connection_id: "audit-client",

        connection_channel: "audit",

        target_channel: "incidents",
      });
    } finally {
      consoleWarn.mockRestore();
    }
  });

  it("does not delete a mismatched-channel connection", async () => {
    const deleted: string[] = [];

    const delivered: string[] = [];

    const consoleWarn = vi.spyOn(console, "warn").mockImplementation(() => {});

    const dependencies = baseDependencies({
      listConnections: async () => [connection("wrong-channel", "audit")],

      deleteConnection: async (connectionId) => {
        deleted.push(connectionId);
      },

      postToConnection: async (target) => {
        delivered.push(target.connection_id);
      },
    });

    try {
      await broadcastIncidentTaskCompletedEvent(notification(), dependencies);

      expect(delivered).toEqual([]);

      expect(deleted).toEqual([]);
    } finally {
      consoleWarn.mockRestore();
    }
  });

  it("removes stale connections after GoneException and continues delivery", async () => {
    const removed: string[] = [];

    const attempted: string[] = [];

    const delivered: string[] = [];

    const dependencies = baseDependencies({
      listConnections: async () => [
        connection("connection-stale"),

        connection("connection-live"),
      ],

      deleteConnection: async (connectionId) => {
        removed.push(connectionId);
      },

      postToConnection: async (target) => {
        attempted.push(target.connection_id);

        if (target.connection_id === "connection-stale") {
          const error = new Error("connection is gone");

          error.name = "GoneException";

          throw error;
        }

        delivered.push(target.connection_id);
      },
    });

    await broadcastIncidentTaskCompletedEvent(notification(), dependencies);

    expect(attempted).toEqual(["connection-stale", "connection-live"]);

    expect(removed).toEqual(["connection-stale"]);

    expect(delivered).toEqual(["connection-live"]);
  });

  it("continues fan-out after a transient connection failure", async () => {
    const attempted: string[] = [];

    const delivered: string[] = [];

    const dependencies = baseDependencies({
      listConnections: async () => [
        connection("connection-a"),

        connection("connection-b"),

        connection("connection-c"),
      ],

      postToConnection: async (target) => {
        attempted.push(target.connection_id);

        if (target.connection_id === "connection-a") {
          throw new Error("temporary API Gateway failure");
        }

        delivered.push(target.connection_id);
      },
    });

    await expect(
      broadcastIncidentTaskCompletedEvent(notification(), dependencies),
    ).rejects.toMatchObject({
      name: "RealtimeFanoutDeliveryError",

      eventId: "7c1f9d0a-f544-47b3-b1df-642875a8fa49",

      failures: [
        {
          connectionId: "connection-a",

          errorType: "Error",

          message: "temporary API Gateway failure",
        },
      ],
    });

    expect(attempted).toEqual(["connection-a", "connection-b", "connection-c"]);

    expect(delivered).toEqual(["connection-b", "connection-c"]);
  });

  it("collects multiple transient delivery failures before rejecting", async () => {
    const attempted: string[] = [];

    const dependencies = baseDependencies({
      listConnections: async () => [
        connection("connection-a"),

        connection("connection-b"),

        connection("connection-c"),
      ],

      postToConnection: async (target) => {
        attempted.push(target.connection_id);

        if (target.connection_id === "connection-a") {
          throw new Error("failure-a");
        }

        if (target.connection_id === "connection-c") {
          const error = new Error("failure-c");

          error.name = "ServiceUnavailableException";

          throw error;
        }
      },
    });

    try {
      await broadcastIncidentTaskCompletedEvent(notification(), dependencies);

      throw new Error("Expected fan-out to fail.");
    } catch (error) {
      expect(error).toBeInstanceOf(RealtimeFanoutDeliveryError);

      if (!(error instanceof RealtimeFanoutDeliveryError)) {
        throw error;
      }

      expect(error.eventId).toBe("7c1f9d0a-f544-47b3-b1df-642875a8fa49");

      expect(error.failures).toEqual([
        {
          connectionId: "connection-a",

          errorType: "Error",

          message: "failure-a",
        },

        {
          connectionId: "connection-c",

          errorType: "ServiceUnavailableException",

          message: "failure-c",
        },
      ]);
    }

    expect(attempted).toEqual(["connection-a", "connection-b", "connection-c"]);
  });

  it("does not fail the notification when stale-connection cleanup fails", async () => {
    const delivered: string[] = [];

    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});

    const dependencies = baseDependencies({
      listConnections: async () => [
        connection("connection-stale"),

        connection("connection-live"),
      ],

      deleteConnection: async () => {
        throw new Error("DynamoDB cleanup failure");
      },

      postToConnection: async (target) => {
        if (target.connection_id === "connection-stale") {
          const error = new Error("connection is gone");

          error.name = "GoneException";

          throw error;
        }

        delivered.push(target.connection_id);
      },
    });

    try {
      await expect(
        broadcastIncidentTaskCompletedEvent(notification(), dependencies),
      ).resolves.toBeUndefined();

      expect(delivered).toEqual(["connection-live"]);

      expect(consoleError).toHaveBeenCalledTimes(1);
    } finally {
      consoleError.mockRestore();
    }
  });

  it("preserves the same event identity across duplicate source deliveries", async () => {
    const payloads: string[] = [];

    const dependencies = baseDependencies({
      listConnections: async () => [connection("connection-a")],

      postToConnection: async (_target, payload) => {
        payloads.push(payload);
      },
    });

    const event = notification();

    await broadcastIncidentTaskCompletedEvent(event, dependencies);

    await broadcastIncidentTaskCompletedEvent(event, dependencies);

    expect(payloads).toHaveLength(2);

    const first = JSON.parse(payloads[0] ?? "{}");

    const second = JSON.parse(payloads[1] ?? "{}");

    expect(first.event_id).toBe(event.event_id);

    expect(second.event_id).toBe(event.event_id);

    expect(second).toEqual(first);
  });
});
