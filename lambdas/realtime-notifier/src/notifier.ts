import {
  ApiGatewayManagementApiClient,
  PostToConnectionCommand,
} from "@aws-sdk/client-apigatewaymanagementapi";

import { deleteConnection, listConnections } from "./connectionStore";

import { validateRealtimeIncidentMessage } from "./notificationContract";

import type {
  ConnectionRecord,
  IncidentTaskCompletedEvent,
  RealtimeIncidentMessage,
} from "./types";

export interface BroadcastDependencies {
  listConnections: () => Promise<ConnectionRecord[]>;

  deleteConnection: (connectionId: string) => Promise<void>;

  postToConnection: (
    connection: ConnectionRecord,
    payload: string,
  ) => Promise<void>;
}

export interface RealtimeConnectionDeliveryFailure {
  connectionId: string;

  errorType: string;

  message: string;
}

export class RealtimeFanoutDeliveryError extends Error {
  readonly eventId: string;

  readonly failures: readonly RealtimeConnectionDeliveryFailure[];

  constructor(
    eventId: string,
    failures: readonly RealtimeConnectionDeliveryFailure[],
  ) {
    const failedConnectionIds = failures
      .map((failure) => failure.connectionId)
      .join(", ");

    super(
      "Realtime notification " +
        `${eventId} failed for ` +
        `${failures.length} connection(s): ` +
        failedConnectionIds,
    );

    this.name = "RealtimeFanoutDeliveryError";

    this.eventId = eventId;

    this.failures = [...failures];
  }
}

const managementClients = new Map<string, ApiGatewayManagementApiClient>();

function buildManagementEndpoint(connection: ConnectionRecord): string {
  return `https://${connection.domain_name}` + `/${connection.stage}`;
}

function getManagementClient(endpoint: string): ApiGatewayManagementApiClient {
  const existing = managementClients.get(endpoint);

  if (existing) {
    return existing;
  }

  const created = new ApiGatewayManagementApiClient({
    endpoint,
  });

  managementClients.set(endpoint, created);

  return created;
}

async function postToConnection(
  connection: ConnectionRecord,
  payload: string,
): Promise<void> {
  const endpoint = buildManagementEndpoint(connection);

  const client = getManagementClient(endpoint);

  await client.send(
    new PostToConnectionCommand({
      ConnectionId: connection.connection_id,

      Data: Buffer.from(payload, "utf8"),
    }),
  );
}

const defaultDependencies: BroadcastDependencies = {
  listConnections,

  deleteConnection,

  postToConnection,
};

function isGoneException(error: unknown): boolean {
  if (typeof error !== "object" || error === null) {
    return false;
  }

  const name = "name" in error ? error.name : undefined;

  return name === "GoneException";
}

function describeError(error: unknown): {
  errorType: string;
  message: string;
} {
  if (error instanceof Error) {
    return {
      errorType: error.name,

      message: error.message,
    };
  }

  return {
    errorType: "UnknownError",

    message: "Unknown delivery error",
  };
}

function logStaleConnectionCleanupFailure(
  connectionId: string,
  error: unknown,
): void {
  const details = describeError(error);

  console.error(
    JSON.stringify({
      level: "error",

      event: "websocket_stale_connection_cleanup_failed",

      connection_id: connectionId,

      error_type: details.errorType,

      error: details.message,
    }),
  );
}

export function buildRealtimeIncidentMessage(
  event: IncidentTaskCompletedEvent,
): RealtimeIncidentMessage {
  return {
    type: "incident.updated",

    schema_version: event.schema_version,

    event_id: event.event_id,

    incident_id: event.incident_id,

    task_id: event.task_id,

    correlation_id: event.correlation_id,

    status: event.status,

    acknowledged_at: event.acknowledged_at,

    occurred_at: event.occurred_at,
  };
}

export async function broadcastIncidentTaskCompletedEvent(
  event: IncidentTaskCompletedEvent,
  dependencies: BroadcastDependencies = defaultDependencies,
): Promise<void> {
  /*
   * Validate the public notification contract before any
   * external delivery-side effect occurs.
   */

  const message = validateRealtimeIncidentMessage(
    buildRealtimeIncidentMessage(event),
  );

  const payload = JSON.stringify(message);

  const connections = await dependencies.listConnections();

  const failures: RealtimeConnectionDeliveryFailure[] = [];

  /*
   * Delivery semantics:
   *
   * 1. Every discovered connection gets an attempt.
   *
   * 2. GoneException means the WebSocket connection is
   *    stale. It is not a transient notification failure.
   *    We remove it and continue.
   *
   * 3. Stale-record cleanup is best effort. Failure to
   *    delete an already-dead connection must not cause the
   *    complete SQS notification to retry, because doing so
   *    would unnecessarily duplicate delivery to healthy
   *    clients.
   *
   * 4. Other delivery failures are transient candidates.
   *    They are collected rather than immediately thrown so
   *    later connections still receive an attempt.
   *
   * 5. After fan-out completes, one aggregate error is
   *    thrown if transient failures occurred. The SQS
   *    handler then reports the source message as a partial
   *    batch failure.
   *
   * 6. SQS delivery is at-least-once. Connections that
   *    succeeded before another connection failed can
   *    receive the same event again on retry.
   *
   *    event_id remains stable across those retries and is
   *    the consumer deduplication identity.
   */

  for (const connection of connections) {
    try {
      await dependencies.postToConnection(connection, payload);
    } catch (error) {
      if (isGoneException(error)) {
        try {
          await dependencies.deleteConnection(connection.connection_id);
        } catch (cleanupError) {
          logStaleConnectionCleanupFailure(
            connection.connection_id,
            cleanupError,
          );
        }

        continue;
      }

      const details = describeError(error);

      failures.push({
        connectionId: connection.connection_id,

        errorType: details.errorType,

        message: details.message,
      });
    }
  }

  if (failures.length > 0) {
    throw new RealtimeFanoutDeliveryError(message.event_id, failures);
  }
}
