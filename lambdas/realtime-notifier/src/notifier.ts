import {
  ApiGatewayManagementApiClient,
  PostToConnectionCommand,
} from "@aws-sdk/client-apigatewaymanagementapi";

import { deleteConnection, listConnections } from "./connectionStore";

import { loadRealtimeNotifierConfig } from "./config";

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

  targetChannel: string;
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

/*
 * Production configuration must be resolved lazily.
 *
 * Unit tests import this module while injecting their own
 * BroadcastDependencies. Loading environment-backed config
 * at module-import time would incorrectly require production
 * Lambda variables before a test can even begin.
 *
 * Creating default dependencies only when they are actually
 * needed preserves:
 *
 *   production config validation
 *
 * while allowing:
 *
 *   deterministic dependency-injected unit tests
 */
function createDefaultDependencies(): BroadcastDependencies {
  const config = loadRealtimeNotifierConfig();

  return {
    listConnections,

    deleteConnection,

    postToConnection,

    targetChannel: config.websocketChannel,
  };
}

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

function logCrossChannelConnectionSkipped(
  connection: ConnectionRecord,
  targetChannel: string,
): void {
  console.warn(
    JSON.stringify({
      level: "warning",

      event: "websocket_cross_channel_connection_skipped",

      connection_id: connection.connection_id,

      connection_channel: connection.channel,

      target_channel: targetChannel,
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
  dependencies?: BroadcastDependencies,
): Promise<void> {
  /*
   * Resolve environment-backed production dependencies only
   * when the caller did not inject its own dependencies.
   *
   * This prevents module imports from requiring Lambda
   * environment variables during isolated unit tests.
   */

  const resolvedDependencies = dependencies ?? createDefaultDependencies();

  const message = validateRealtimeIncidentMessage(
    buildRealtimeIncidentMessage(event),
  );

  const payload = JSON.stringify(message);

  const connections = await resolvedDependencies.listConnections();

  const failures: RealtimeConnectionDeliveryFailure[] = [];

  for (const connection of connections) {
    /*
     * The persistence layer already queries DynamoDB using
     * the configured channel partition.
     *
     * This second check is intentional defense in depth.
     */

    if (connection.channel !== resolvedDependencies.targetChannel) {
      logCrossChannelConnectionSkipped(
        connection,
        resolvedDependencies.targetChannel,
      );

      continue;
    }

    try {
      await resolvedDependencies.postToConnection(connection, payload);
    } catch (error) {
      if (isGoneException(error)) {
        try {
          await resolvedDependencies.deleteConnection(connection.connection_id);
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
