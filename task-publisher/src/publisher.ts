import type {
  SendMessageCommandInput,
  SendMessageCommandOutput,
} from "@aws-sdk/client-sqs";

import { loadPublisherConfig, type PublisherConfig } from "./config";
import { createTaskEnvelope, type TaskEnvelope } from "./taskEnvelope";
import { assertValidTaskEnvelope } from "./validation";
import { sendSqsMessage } from "./sqsClient";

export interface PublishTaskInput {
  taskType: string;
  idempotencyKey: string;
  payload: Record<string, unknown>;
  correlationId?: string;
  causationId?: string | null;
  metadata?: Record<string, string>;
}

export interface PublishTaskResult {
  messageId: string;
  envelope: TaskEnvelope;
}

export type SendMessageFunction = (
  input: SendMessageCommandInput,
) => Promise<SendMessageCommandOutput>;

export interface PublishTaskDependencies {
  config?: PublisherConfig;
  sendMessage?: SendMessageFunction;
}

export async function publishTask(
  input: PublishTaskInput,
  dependencies: PublishTaskDependencies = {},
): Promise<PublishTaskResult> {
  const config = dependencies.config ?? loadPublisherConfig();

  const sendMessage = dependencies.sendMessage ?? sendSqsMessage;

  const envelope = createTaskEnvelope({
    taskType: input.taskType,
    producer: config.producerName,
    idempotencyKey: input.idempotencyKey,
    payload: input.payload,
    correlationId: input.correlationId,
    causationId: input.causationId,
    metadata: input.metadata,
  });

  assertValidTaskEnvelope(envelope);

  const response = await sendMessage({
    QueueUrl: config.taskQueueUrl,
    MessageBody: JSON.stringify(envelope),
    MessageAttributes: {
      task_type: {
        DataType: "String",
        StringValue: envelope.task_type,
      },
      schema_version: {
        DataType: "String",
        StringValue: envelope.schema_version,
      },
      correlation_id: {
        DataType: "String",
        StringValue: envelope.correlation_id,
      },
    },
  });

  if (!response.MessageId) {
    throw new Error("Amazon SQS did not return a MessageId");
  }

  return {
    messageId: response.MessageId,
    envelope,
  };
}
