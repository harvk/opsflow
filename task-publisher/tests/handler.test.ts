import type {
  SendMessageCommandInput,
  SendMessageCommandOutput,
} from "@aws-sdk/client-sqs";

import { describe, expect, it } from "vitest";

import { publishTask } from "../src/publisher";

describe("publishTask", () => {
  it("validates and sends a task to the configured queue", async () => {
    const sentMessages: SendMessageCommandInput[] = [];

    const sendMessage = async (
      input: SendMessageCommandInput,
    ): Promise<SendMessageCommandOutput> => {
      sentMessages.push(input);

      return {
        MessageId: "sqs-message-123",
        $metadata: {},
      };
    };

    const result = await publishTask(
      {
        taskType: "incident.notification.requested",
        idempotencyKey: "incident:123:notification:opened",
        payload: {
          incident_id: 123,
          notification_type: "incident-opened",
        },
        metadata: {
          environment: "test",
        },
      },
      {
        config: {
          taskQueueUrl:
            "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
          producerName: "opsflow-task-publisher",
        },
        sendMessage,
      },
    );

    expect(result.messageId).toBe("sqs-message-123");

    expect(sentMessages).toHaveLength(1);

    const sent = sentMessages[0];

    expect(sent.QueueUrl).toContain("test-queue");

    const body = JSON.parse(sent.MessageBody ?? "{}");

    expect(body.task_id).toBe(result.envelope.task_id);

    expect(body.task_type).toBe("incident.notification.requested");

    expect(body.idempotency_key).toBe("incident:123:notification:opened");

    expect(body.producer).toBe("opsflow-task-publisher");

    expect(sent.MessageAttributes?.task_type?.StringValue).toBe(
      "incident.notification.requested",
    );
  });

  it("creates different message identities for duplicate logical operations", async () => {
    const sendMessage = async (
      _input: SendMessageCommandInput,
    ): Promise<SendMessageCommandOutput> => ({
      MessageId: "test-message",
      $metadata: {},
    });

    const dependencies = {
      config: {
        taskQueueUrl:
          "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
        producerName: "opsflow-task-publisher",
      },
      sendMessage,
    };

    const input = {
      taskType: "incident.notification.requested",
      idempotencyKey: "incident:123:notification:opened",
      payload: {
        incident_id: 123,
      },
    };

    const first = await publishTask(input, dependencies);

    const second = await publishTask(input, dependencies);

    expect(first.envelope.task_id).not.toBe(second.envelope.task_id);

    expect(first.envelope.idempotency_key).toBe(
      second.envelope.idempotency_key,
    );
  });

  it("fails if SQS does not return a MessageId", async () => {
    const sendMessage = async (
      _input: SendMessageCommandInput,
    ): Promise<SendMessageCommandOutput> => ({
      $metadata: {},
    });

    await expect(
      publishTask(
        {
          taskType: "incident.notification.requested",
          idempotencyKey: "incident:123:notification:opened",
          payload: {
            incident_id: 123,
          },
        },
        {
          config: {
            taskQueueUrl:
              "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
            producerName: "opsflow-task-publisher",
          },
          sendMessage,
        },
      ),
    ).rejects.toThrow("Amazon SQS did not return a MessageId");
  });
});
