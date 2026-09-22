import type {
  SQSEvent,
  SQSRecord,
} from "aws-lambda";

import {
  describe,
  expect,
  it,
} from "vitest";

import {
  createHandler,
} from "../src/handler";

import type {
  WebhookProductionDependencies,
} from "../src/handler";

const SIGNING_SECRET =
  "opsflow-test-webhook-secret-0123456789abcdef";

function notification(
  eventId:
    string,
): Record<string, unknown> {
  return {
    type:
      "incident.updated",

    schema_version:
      "1.0",

    event_id:
      eventId,

    incident_id:
      "aca0a505-b460-4d08-9035-3b92bac0fff1",

    task_id:
      "bb587a5f-3c94-4e03-8b13-159d8f58acfa",

    correlation_id:
      "phase-11-5g-4f5",

    status:
      "Investigating",

    acknowledged_at:
      "2026-09-22T14:00:00Z",

    occurred_at:
      "2026-09-22T14:00:01Z",
  };
}

function sqsRecord(
  messageId:
    string,

  body:
    string,
): SQSRecord {
  return {
    messageId,

    receiptHandle:
      `receipt-${messageId}`,

    body,

    attributes: {
      ApproximateReceiveCount:
        "1",

      SentTimestamp:
        "1790085600000",

      SenderId:
        "opsflow-tests",

      ApproximateFirstReceiveTimestamp:
        "1790085600000",
    },

    messageAttributes:
      {},

    md5OfBody:
      "test-md5",

    eventSource:
      "aws:sqs",

    eventSourceARN:
      "arn:aws:sqs:us-east-1:"
      + "123456789012:"
      + "opsflow-dev-webhook-notification-queue",

    awsRegion:
      "us-east-1",
  };
}

function event(
  messageId:
    string,

  eventId:
    string,
): SQSEvent {
  return {
    Records: [
      sqsRecord(
        messageId,
        JSON.stringify(
          notification(
            eventId,
          ),
        ),
      ),
    ],
  };
}

describe(
  "production webhook Lambda handler",
  () => {
    it(
      "loads runtime configuration once per warm handler instance",
      async () => {
        let configLoads =
          0;

        const delivered:
          string[] = [];

        const dependencies:
          WebhookProductionDependencies = {
          loadConfig:
            async () => {
              configLoads +=
                1;

              return {
                targetUrl:
                  "https://example.com/hooks/incidents",

                signingSecret:
                  SIGNING_SECRET,

                timeoutMs:
                  5000,
              };
            },

          nowSeconds:
            () =>
              1790085600,

          fetchImpl:
            async (
              _input,
              init,
            ) => {
              const body =
                JSON.parse(
                  String(
                    init?.body
                    ?? "{}",
                  ),
                );

              delivered.push(
                String(
                  body.event_id,
                ),
              );

              return new Response(
                null,
                {
                  status:
                    204,
                },
              );
            },
        };

        const handler =
          createHandler(
            dependencies,
          );

        await handler(
          event(
            "message-1",
            "7c1f9d0a-f544-47b3-b1df-642875a8fa49",
          ),
        );

        await handler(
          event(
            "message-2",
            "29c43085-9e80-4df6-bef7-09d24ca97570",
          ),
        );

        expect(
          configLoads,
        ).toBe(
          1,
        );

        expect(
          delivered,
        ).toEqual([
          "7c1f9d0a-f544-47b3-b1df-642875a8fa49",
          "29c43085-9e80-4df6-bef7-09d24ca97570",
        ]);
      },
    );

    it(
      "retries configuration loading after a transient load failure",
      async () => {
        let configLoads =
          0;

        const dependencies:
          WebhookProductionDependencies = {
          loadConfig:
            async () => {
              configLoads +=
                1;

              if (
                configLoads === 1
              ) {
                throw new Error(
                  "synthetic Secrets Manager failure",
                );
              }

              return {
                targetUrl:
                  "https://example.com/hooks/incidents",

                signingSecret:
                  SIGNING_SECRET,

                timeoutMs:
                  5000,
              };
            },

          nowSeconds:
            () =>
              1790085600,

          fetchImpl:
            async () =>
              new Response(
                null,
                {
                  status:
                    204,
                },
              ),
        };

        const handler =
          createHandler(
            dependencies,
          );

        await expect(
          handler(
            event(
              "message-1",
              "7c1f9d0a-f544-47b3-b1df-642875a8fa49",
            ),
          ),
        ).rejects.toThrow(
          "synthetic Secrets Manager failure",
        );

        await expect(
          handler(
            event(
              "message-2",
              "29c43085-9e80-4df6-bef7-09d24ca97570",
            ),
          ),
        ).resolves.toEqual({
          batchItemFailures:
            [],
        });

        expect(
          configLoads,
        ).toBe(
          2,
        );
      },
    );
  },
);
