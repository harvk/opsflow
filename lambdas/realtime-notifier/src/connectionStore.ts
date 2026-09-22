import { DynamoDBClient } from "@aws-sdk/client-dynamodb";

import {
  DeleteCommand,
  DynamoDBDocumentClient,
  PutCommand,
  QueryCommand,
} from "@aws-sdk/lib-dynamodb";

import { loadRealtimeNotifierConfig } from "./config";

import type { ConnectionRecord, SaveConnectionInput } from "./types";

const documentClient = DynamoDBDocumentClient.from(new DynamoDBClient({}));

function requireStoredString(value: unknown, field: string): string {
  if (typeof value !== "string" || value.length === 0) {
    throw new Error(`Stored WebSocket connection is missing ${field}`);
  }

  return value;
}

function requireStoredNumber(value: unknown, field: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new Error(`Stored WebSocket connection is missing ${field}`);
  }

  return value;
}

function toConnectionRecord(item: Record<string, unknown>): ConnectionRecord {
  return {
    channel: requireStoredString(item.channel, "channel"),

    connection_id: requireStoredString(item.connection_id, "connection_id"),

    domain_name: requireStoredString(item.domain_name, "domain_name"),

    stage: requireStoredString(item.stage, "stage"),

    connected_at: requireStoredString(item.connected_at, "connected_at"),

    expires_at: requireStoredNumber(item.expires_at, "expires_at"),
  };
}

export async function saveConnection(
  input: SaveConnectionInput,
): Promise<void> {
  const config = loadRealtimeNotifierConfig();

  const now = new Date();

  const expiresAt =
    Math.floor(now.getTime() / 1000) + config.connectionTtlSeconds;

  const record: ConnectionRecord = {
    channel: config.websocketChannel,

    connection_id: input.connectionId,

    domain_name: input.domainName,

    stage: input.stage,

    connected_at: now.toISOString(),

    expires_at: expiresAt,
  };

  await documentClient.send(
    new PutCommand({
      TableName: config.connectionsTableName,

      Item: record,
    }),
  );
}

export async function deleteConnection(connectionId: string): Promise<void> {
  const config = loadRealtimeNotifierConfig();

  await documentClient.send(
    new DeleteCommand({
      TableName: config.connectionsTableName,

      Key: {
        channel: config.websocketChannel,

        connection_id: connectionId,
      },
    }),
  );
}

export async function listConnections(): Promise<ConnectionRecord[]> {
  const config = loadRealtimeNotifierConfig();

  const connections: ConnectionRecord[] = [];

  let exclusiveStartKey: Record<string, unknown> | undefined;

  do {
    const response = await documentClient.send(
      new QueryCommand({
        TableName: config.connectionsTableName,

        KeyConditionExpression: "#channel = :channel",

        ExpressionAttributeNames: {
          "#channel": "channel",
        },

        ExpressionAttributeValues: {
          ":channel": config.websocketChannel,
        },

        ExclusiveStartKey: exclusiveStartKey,
      }),
    );

    for (const item of response.Items ?? []) {
      connections.push(toConnectionRecord(item));
    }

    exclusiveStartKey = response.LastEvaluatedKey;
  } while (exclusiveStartKey);

  return connections;
}
