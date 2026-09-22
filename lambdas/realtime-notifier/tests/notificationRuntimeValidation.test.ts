import { describe, expect, it } from "vitest";

import {
  InvalidRealtimeNotificationError,
  validateRealtimeIncidentMessage,
} from "../src/notificationContract";

import {
  broadcastIncidentTaskCompletedEvent,
  buildRealtimeIncidentMessage,
} from "../src/notifier";

import type { BroadcastDependencies } from "../src/notifier";

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

    correlation_id: "phase-11-5g-4e2-runtime-validation",

    status: "Investigating",

    acknowledged_at: "2026-09-21T16:00:00Z",

    occurred_at: "2026-09-21T16:00:01Z",
  };
}

describe("realtime notification runtime validation", () => {
  it("accepts the real notifier builder output", () => {
    const message = buildRealtimeIncidentMessage(completedEvent());

    expect(validateRealtimeIncidentMessage(message)).toEqual(message);
  });

  it("rejects an outbound message with an invalid status", () => {
    const invalidMessage = {
      ...buildRealtimeIncidentMessage(completedEvent()),

      status: "Deleted",
    } as unknown as RealtimeIncidentMessage;

    expect(() => validateRealtimeIncidentMessage(invalidMessage)).toThrow(
      InvalidRealtimeNotificationError,
    );
  });

  it("rejects an outbound message with an empty correlation identifier", () => {
    const invalidMessage = {
      ...buildRealtimeIncidentMessage(completedEvent()),

      correlation_id: "",
    } as RealtimeIncidentMessage;

    expect(() => validateRealtimeIncidentMessage(invalidMessage)).toThrow(
      InvalidRealtimeNotificationError,
    );
  });

  it("does not discover connections or deliver when the outbound contract is invalid", async () => {
    let listConnectionsCalls = 0;

    let postToConnectionCalls = 0;

    let deleteConnectionCalls = 0;

    const dependencies: BroadcastDependencies = {
      listConnections: async () => {
        listConnectionsCalls += 1;

        return [];
      },

      postToConnection: async () => {
        postToConnectionCalls += 1;
      },

      deleteConnection: async () => {
        deleteConnectionCalls += 1;
      },
    };

    const invalidEvent = {
      ...completedEvent(),

      correlation_id: "",
    } as IncidentTaskCompletedEvent;

    await expect(
      broadcastIncidentTaskCompletedEvent(invalidEvent, dependencies),
    ).rejects.toBeInstanceOf(InvalidRealtimeNotificationError);

    expect(listConnectionsCalls).toBe(0);

    expect(postToConnectionCalls).toBe(0);

    expect(deleteConnectionCalls).toBe(0);
  });
});
