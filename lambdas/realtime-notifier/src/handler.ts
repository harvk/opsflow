import { deleteConnection, saveConnection } from "./connectionStore";

import { parseIncidentTaskCompletedEvent } from "./notification";

import { broadcastIncidentTaskCompletedEvent } from "./notifier";

import type {
  IncidentTaskCompletedEvent,
  SaveConnectionInput,
  SqsBatchResponse,
  WebSocketResponse,
} from "./types";

interface UnknownRecord {
  [key: string]: unknown;
}

interface SqsRecord {
  messageId: string;

  body: string;
}

interface WebSocketRequestContext {
  routeKey: string;

  connectionId: string;

  domainName: string;

  stage: string;
}

interface WebSocketEvent {
  requestContext: WebSocketRequestContext;
}

export interface HandlerDependencies {
  saveConnection: (input: SaveConnectionInput) => Promise<void>;

  deleteConnection: (connectionId: string) => Promise<void>;

  broadcastNotification: (event: IncidentTaskCompletedEvent) => Promise<void>;
}

export type HandlerResult = WebSocketResponse | SqsBatchResponse;

const defaultDependencies: HandlerDependencies = {
  saveConnection,

  deleteConnection,

  broadcastNotification: broadcastIncidentTaskCompletedEvent,
};

function isObject(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isSqsEvent(event: unknown): event is {
  Records: unknown[];
} {
  if (!isObject(event)) {
    return false;
  }

  return Array.isArray(event.Records);
}

function parseSqsRecord(value: unknown): SqsRecord {
  if (!isObject(value)) {
    throw new Error("SQS record must be an object");
  }

  const messageId = value.messageId;

  const body = value.body;

  if (typeof messageId !== "string" || messageId.length === 0) {
    throw new Error("SQS record must contain messageId");
  }

  if (typeof body !== "string") {
    throw new Error("SQS record must contain body");
  }

  return {
    messageId,
    body,
  };
}

function parseWebSocketEvent(event: unknown): WebSocketEvent {
  if (!isObject(event)) {
    throw new Error("WebSocket event must be an object");
  }

  const requestContext = event.requestContext;

  if (!isObject(requestContext)) {
    throw new Error("WebSocket event must contain requestContext");
  }

  const routeKey = requestContext.routeKey;

  const connectionId = requestContext.connectionId;

  const domainName = requestContext.domainName;

  const stage = requestContext.stage;

  if (typeof routeKey !== "string" || routeKey.length === 0) {
    throw new Error("WebSocket requestContext must contain routeKey");
  }

  if (typeof connectionId !== "string" || connectionId.length === 0) {
    throw new Error("WebSocket requestContext must contain connectionId");
  }

  if (typeof domainName !== "string" || domainName.length === 0) {
    throw new Error("WebSocket requestContext must contain domainName");
  }

  if (typeof stage !== "string" || stage.length === 0) {
    throw new Error("WebSocket requestContext must contain stage");
  }

  return {
    requestContext: {
      routeKey,
      connectionId,
      domainName,
      stage,
    },
  };
}

function structuredLog(
  level: "info" | "error",
  event: string,
  fields: Record<string, unknown> = {},
): void {
  const entry = JSON.stringify({
    level,
    event,
    ...fields,
  });

  if (level === "error") {
    console.error(entry);

    return;
  }

  console.log(entry);
}

async function handleSqsEvent(
  event: {
    Records: unknown[];
  },
  dependencies: HandlerDependencies,
): Promise<SqsBatchResponse> {
  const batchItemFailures: {
    itemIdentifier: string;
  }[] = [];

  for (const candidate of event.Records) {
    let messageId = "unknown";

    try {
      const record = parseSqsRecord(candidate);

      messageId = record.messageId;

      const notification = parseIncidentTaskCompletedEvent(record.body);

      await dependencies.broadcastNotification(notification);

      structuredLog("info", "realtime_notification_delivered", {
        sqs_message_id: record.messageId,

        event_id: notification.event_id,

        incident_id: notification.incident_id,

        task_id: notification.task_id,

        correlation_id: notification.correlation_id,
      });
    } catch (error) {
      structuredLog("error", "realtime_notification_failed", {
        sqs_message_id: messageId,

        error_type: error instanceof Error ? error.name : "UnknownError",

        error: error instanceof Error ? error.message : "Unknown error",
      });

      if (messageId !== "unknown") {
        batchItemFailures.push({
          itemIdentifier: messageId,
        });
      } else {
        throw error;
      }
    }
  }

  return {
    batchItemFailures,
  };
}

async function handleWebSocketEvent(
  event: unknown,
  dependencies: HandlerDependencies,
): Promise<WebSocketResponse> {
  const websocketEvent = parseWebSocketEvent(event);

  const { routeKey, connectionId, domainName, stage } =
    websocketEvent.requestContext;

  if (routeKey === "$connect") {
    await dependencies.saveConnection({
      connectionId,
      domainName,
      stage,
    });

    structuredLog("info", "websocket_connected", {
      connection_id: connectionId,

      domain_name: domainName,

      stage,
    });

    return {
      statusCode: 200,
    };
  }

  if (routeKey === "$disconnect") {
    await dependencies.deleteConnection(connectionId);

    structuredLog("info", "websocket_disconnected", {
      connection_id: connectionId,
    });

    return {
      statusCode: 200,
    };
  }

  structuredLog("info", "websocket_route_ignored", {
    connection_id: connectionId,

    route_key: routeKey,
  });

  return {
    statusCode: 200,

    body: JSON.stringify({
      status: "ignored",
    }),
  };
}

export function createHandler(
  dependencies: HandlerDependencies = defaultDependencies,
) {
  return async function handler(event: unknown): Promise<HandlerResult> {
    if (isSqsEvent(event)) {
      return handleSqsEvent(event, dependencies);
    }

    return handleWebSocketEvent(event, dependencies);
  };
}

export const handler = createHandler();
