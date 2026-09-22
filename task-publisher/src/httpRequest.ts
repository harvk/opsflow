import type { APIGatewayProxyEventV2 } from "aws-lambda";

import type { PublishTaskInput } from "./publisher";

export class BadRequestError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "BadRequestError";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function requireNonEmptyString(value: unknown, fieldName: string): string {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new BadRequestError(`${fieldName} must be a non-empty string`);
  }

  return value.trim();
}

function parseMetadata(value: unknown): Record<string, string> | undefined {
  if (value === undefined) {
    return undefined;
  }

  if (!isRecord(value)) {
    throw new BadRequestError("metadata must be an object");
  }

  const metadata: Record<string, string> = {};

  for (const [key, metadataValue] of Object.entries(value)) {
    if (typeof metadataValue !== "string") {
      throw new BadRequestError(`metadata.${key} must be a string`);
    }

    metadata[key] = metadataValue;
  }

  return metadata;
}

function decodeRequestBody(event: APIGatewayProxyEventV2): string {
  if (!event.body) {
    throw new BadRequestError("Request body is required");
  }

  if (event.isBase64Encoded) {
    return Buffer.from(event.body, "base64").toString("utf8");
  }

  return event.body;
}

export function parsePublishTaskRequest(
  event: APIGatewayProxyEventV2,
): PublishTaskInput {
  const bodyText = decodeRequestBody(event);

  let parsed: unknown;

  try {
    parsed = JSON.parse(bodyText);
  } catch {
    throw new BadRequestError("Request body must contain valid JSON");
  }

  if (!isRecord(parsed)) {
    throw new BadRequestError("Request body must be a JSON object");
  }

  const allowedFields = new Set([
    "task_type",
    "idempotency_key",
    "payload",
    "correlation_id",
    "causation_id",
    "metadata",
  ]);

  for (const field of Object.keys(parsed)) {
    if (!allowedFields.has(field)) {
      throw new BadRequestError(`Unexpected request field: ${field}`);
    }
  }

  const taskType = requireNonEmptyString(parsed.task_type, "task_type");

  const idempotencyKey = requireNonEmptyString(
    parsed.idempotency_key,
    "idempotency_key",
  );

  if (!isRecord(parsed.payload)) {
    throw new BadRequestError("payload must be a JSON object");
  }

  let correlationId: string | undefined;

  if (parsed.correlation_id !== undefined) {
    correlationId = requireNonEmptyString(
      parsed.correlation_id,
      "correlation_id",
    );
  }

  let causationId: string | null | undefined;

  if (parsed.causation_id === null) {
    causationId = null;
  } else if (parsed.causation_id !== undefined) {
    causationId = requireNonEmptyString(parsed.causation_id, "causation_id");
  }

  const metadata = parseMetadata(parsed.metadata);

  return {
    taskType,
    idempotencyKey,
    payload: parsed.payload,
    correlationId,
    causationId,
    metadata,
  };
}
