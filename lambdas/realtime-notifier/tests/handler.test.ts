import { describe, expect, it } from "vitest";

import { createHandler, type HandlerDependencies } from "../src/handler";

import type {
  IncidentTaskCompletedEvent,
  SaveConnectionInput,
} from "../src/types";

function validNotification(): IncidentTaskCompletedEvent {
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

function buildDependencies(): {
  dependencies: HandlerDependencies;

  savedConnections: SaveConnectionInput[];

  deletedConnections: string[];

  dispatchedNotifications: IncidentTaskCompletedEvent[];
} {
  const savedConnections: SaveConnectionInput[] = [];

  const deletedConnections: string[] = [];

  const dispatchedNotifications: IncidentTaskCompletedEvent[] = [];

  return {
    savedConnections,

    deletedConnections,

    dispatchedNotifications,

    dependencies: {
      saveConnection: async (input: SaveConnectionInput): Promise<void> => {
        savedConnections.push(input);
      },

      deleteConnection: async (connectionId: string): Promise<void> => {
        deletedConnections.push(connectionId);
      },

      dispatchNotification: async (
        notification: IncidentTaskCompletedEvent,
      ): Promise<void> => {
        dispatchedNotifications.push(notification);
      },
    },
  };
}

describe("realtime notifier handler", () => {
  it("stores a WebSocket connection", async () => {
    const { dependencies, savedConnections } = buildDependencies();

    const handler = createHandler(dependencies);

    const result = await handler({
      requestContext: {
        routeKey: "$connect",

        connectionId: "connection-123",

        domainName: "abc123.execute-api.us-east-1.amazonaws.com",

        stage: "dev",
      },
    });

    expect(result).toEqual({
      statusCode: 200,
    });

    expect(savedConnections).toEqual([
      {
        connectionId: "connection-123",

        domainName: "abc123.execute-api.us-east-1.amazonaws.com",

        stage: "dev",
      },
    ]);
  });

  it("removes a disconnected WebSocket connection", async () => {
    const { dependencies, deletedConnections } = buildDependencies();

    const handler = createHandler(dependencies);

    const result = await handler({
      requestContext: {
        routeKey: "$disconnect",

        connectionId: "connection-456",

        domainName: "abc123.execute-api.us-east-1.amazonaws.com",

        stage: "dev",
      },
    });

    expect(result).toEqual({
      statusCode: 200,
    });

    expect(deletedConnections).toEqual(["connection-456"]);
  });

  it("dispatches a valid completed incident event", async () => {
    const { dependencies, dispatchedNotifications } = buildDependencies();

    const handler = createHandler(dependencies);

    const notification = validNotification();

    const result = await handler({
      Records: [
        {
          messageId: "message-1",

          body: JSON.stringify(notification),
        },
      ],
    });

    expect(result).toEqual({
      batchItemFailures: [],
    });

    expect(dispatchedNotifications).toEqual([notification]);
  });

  it("reports malformed notification records as partial batch failures", async () => {
    const { dependencies, dispatchedNotifications } = buildDependencies();

    const handler = createHandler(dependencies);

    const result = await handler({
      Records: [
        {
          messageId: "message-bad",

          body: "{invalid-json",
        },
      ],
    });

    expect(result).toEqual({
      batchItemFailures: [
        {
          itemIdentifier: "message-bad",
        },
      ],
    });

    expect(dispatchedNotifications).toEqual([]);
  });

  it("reports dispatch failures without failing unrelated records", async () => {
    const delivered: string[] = [];

    let attempts = 0;

    const dependencies: HandlerDependencies = {
      saveConnection: async () => {},

      deleteConnection: async () => {},

      dispatchNotification: async (notification) => {
        attempts += 1;

        if (attempts === 1) {
          throw new Error("simulated dispatch failure");
        }

        delivered.push(notification.event_id);
      },
    };

    const handler = createHandler(dependencies);

    const first = validNotification();

    const second = {
      ...validNotification(),

      event_id: "d5a262f5-c65e-4afe-977c-eb4442d6b521",
    };

    const result = await handler({
      Records: [
        {
          messageId: "message-failed",

          body: JSON.stringify(first),
        },

        {
          messageId: "message-success",

          body: JSON.stringify(second),
        },
      ],
    });

    expect(result).toEqual({
      batchItemFailures: [
        {
          itemIdentifier: "message-failed",
        },
      ],
    });

    expect(delivered).toEqual([second.event_id]);
  });
});
