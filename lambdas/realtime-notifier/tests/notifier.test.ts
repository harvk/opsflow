import { describe, expect, it } from "vitest";

import {
  broadcastIncidentTaskCompletedEvent,
  type BroadcastDependencies,
} from "../src/notifier";

import type {
  ConnectionRecord,
  IncidentTaskCompletedEvent,
} from "../src/types";

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

function connection(connectionId: string): ConnectionRecord {
  return {
    channel: "incidents",

    connection_id: connectionId,

    domain_name: "abc123.execute-api.us-east-1.amazonaws.com",

    stage: "dev",

    connected_at: "2026-09-21T16:00:00Z",

    expires_at: 1790000000,
  };
}

describe("broadcastIncidentTaskCompletedEvent", () => {
  it("delivers the incident update to every active connection", async () => {
    const sent: {
      connectionId: string;
      payload: string;
    }[] = [];

    const dependencies: BroadcastDependencies = {
      listConnections: async () => [
        connection("connection-a"),

        connection("connection-b"),
      ],

      deleteConnection: async () => {},

      postToConnection: async (target, payload) => {
        sent.push({
          connectionId: target.connection_id,

          payload,
        });
      },
    };

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

  it("removes stale connections after GoneException", async () => {
    const removed: string[] = [];

    const delivered: string[] = [];

    const dependencies: BroadcastDependencies = {
      listConnections: async () => [
        connection("connection-stale"),

        connection("connection-live"),
      ],

      deleteConnection: async (connectionId) => {
        removed.push(connectionId);
      },

      postToConnection: async (target) => {
        if (target.connection_id === "connection-stale") {
          const error = new Error("connection is gone");

          error.name = "GoneException";

          throw error;
        }

        delivered.push(target.connection_id);
      },
    };

    await broadcastIncidentTaskCompletedEvent(notification(), dependencies);

    expect(removed).toEqual(["connection-stale"]);

    expect(delivered).toEqual(["connection-live"]);
  });

  it("propagates transient delivery failures for SQS retry", async () => {
    const dependencies: BroadcastDependencies = {
      listConnections: async () => [connection("connection-a")],

      deleteConnection: async () => {},

      postToConnection: async () => {
        throw new Error("temporary API Gateway failure");
      },
    };

    await expect(
      broadcastIncidentTaskCompletedEvent(notification(), dependencies),
    ).rejects.toThrow("temporary API Gateway failure");
  });
});
