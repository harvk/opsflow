import type {
  APIGatewayProxyEventV2,
  APIGatewayProxyStructuredResultV2,
} from "aws-lambda";

import { BadRequestError, parsePublishTaskRequest } from "./httpRequest";

import {
  publishTask,
  type PublishTaskInput,
  type PublishTaskResult,
} from "./publisher";

import { InvalidTaskEnvelopeError } from "./validation";

export interface HandlerDependencies {
  publishTask: (input: PublishTaskInput) => Promise<PublishTaskResult>;
}

const defaultDependencies: HandlerDependencies = {
  publishTask,
};

function jsonResponse(
  statusCode: number,
  body: Record<string, unknown>,
): APIGatewayProxyStructuredResultV2 {
  return {
    statusCode,
    headers: {
      "content-type": "application/json",
    },
    body: JSON.stringify(body),
  };
}

export function createHandler(
  dependencies: HandlerDependencies = defaultDependencies,
) {
  return async function handler(
    event: APIGatewayProxyEventV2,
  ): Promise<APIGatewayProxyStructuredResultV2> {
    try {
      const request = parsePublishTaskRequest(event);

      const result = await dependencies.publishTask(request);

      console.log(
        JSON.stringify({
          level: "info",
          event: "task_published",
          task_id: result.envelope.task_id,
          task_type: result.envelope.task_type,
          correlation_id: result.envelope.correlation_id,
          idempotency_key: result.envelope.idempotency_key,
          sqs_message_id: result.messageId,
        }),
      );

      return jsonResponse(202, {
        status: "accepted",
        task_id: result.envelope.task_id,
        correlation_id: result.envelope.correlation_id,
        idempotency_key: result.envelope.idempotency_key,
      });
    } catch (error) {
      if (
        error instanceof BadRequestError ||
        error instanceof InvalidTaskEnvelopeError
      ) {
        return jsonResponse(400, {
          error: "bad_request",
          message: error.message,
        });
      }

      console.error(
        JSON.stringify({
          level: "error",
          event: "task_publish_failed",
          error: error instanceof Error ? error.message : "Unknown error",
        }),
      );

      return jsonResponse(503, {
        error: "task_publish_failed",
        message: "Task could not be accepted for asynchronous processing",
      });
    }
  };
}

export const handler = createHandler();
