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
  const message = validateRealtimeIncidentMessage(
    buildRealtimeIncidentMessage(event),
  );

  const payload = JSON.stringify(message);

  /*
   * Contract validation intentionally occurs BEFORE
   * connection discovery.
   *
   * An invalid outbound notification therefore produces:
   *
   *   zero DynamoDB connection-list reads
   *   zero WebSocket delivery attempts
   *   zero stale-connection deletions
   *
   * The SQS handler can then return the source record as a
   * batch-item failure and allow the existing retry/DLQ
   * policy to handle the failed notification.
   */

  const connections = await dependencies.listConnections();

  for (const connection of connections) {
    try {
      await dependencies.postToConnection(connection, payload);
    } catch (error) {
      if (isGoneException(error)) {
        await dependencies.deleteConnection(connection.connection_id);

        continue;
      }

      throw error;
    }
  }
}
