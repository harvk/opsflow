import { describe, expect, it } from "vitest";

import { handleWebhookBatch } from "../src/handler";

import type { WebhookBatchDependencies } from "../src/handler";

import type { SQSEvent, SQSRecord } from "aws-lambda";

const SECRET = "opsflow-test-webhook-secret-0123456789abcdef";

function notification(eventId: string): Record<string, unknown> {
  return {
    type: "incident.updated",

    schema_version: "1.0",

    event_id: eventId,

    incident_id: "aca0a505-b460-4d08-9035-3b92bac0fff1",

    task_id: "bb587a5f-3c94-4e03-8b13-159d8f58acfa",

    correlation_id: "phase-11-5g-4f3",

    status: "Investigating",

    acknowledged_at: "2026-09-22T14:00:00Z",

    occurred_at: "2026-09-22T14:00:01Z",
  };
}

function sqsRecord(
  messageId: string,

  body: string,
): SQSRecord {
  return {
    messageId,

    receiptHandle: `receipt-${messageId}`,

    body,

    attributes: {
      ApproximateReceiveCount: "1",

      SentTimestamp: "1790085600000",

      SenderId: "opsflow-tests",

      ApproximateFirstReceiveTimestamp: "1790085600000",
    },

    messageAttributes: {},

    md5OfBody: "test-md5",

    eventSource: "aws:sqs",

    eventSourceARN:
      "arn:aws:sqs:us-east-1:" + "123456789012:" + "opsflow-test-webhook-queue",

    awsRegion: "us-east-1",
  };
}

function event(records: SQSRecord[]): SQSEvent {
  return {
    Records: records,
  };
}

function dependencies(
  fetchImpl: typeof fetch,

  nowSeconds: () => number = () => 1790085600,
): WebhookBatchDependencies {
  return {
    target: {
      url: "https://example.com/hooks/incidents",
    },

    signingSecret: SECRET,

    timeoutMs: 5_000,

    nowSeconds,

    fetchImpl,
  };
}

describe("handleWebhookBatch", () => {
  it("delivers every successful SQS record", async () => {
    const delivered: string[] = [];

    const fetchImpl: typeof fetch = async (_input, init) => {
      const body = JSON.parse(String(init?.body ?? "{}"));

      delivered.push(String(body.event_id));

      return new Response(null, {
        status: 204,
      });
    };

    const result = await handleWebhookBatch(
      event([
        sqsRecord(
          "message-a",
          JSON.stringify(notification("7c1f9d0a-f544-47b3-b1df-642875a8fa49")),
        ),

        sqsRecord(
          "message-b",
          JSON.stringify(notification("29c43085-9e80-4df6-bef7-09d24ca97570")),
        ),
      ]),
      dependencies(fetchImpl),
    );

    expect(result).toEqual({
      batchItemFailures: [],
    });

    expect(delivered).toEqual([
      "7c1f9d0a-f544-47b3-b1df-642875a8fa49",
      "29c43085-9e80-4df6-bef7-09d24ca97570",
    ]);
  });

  it("isolates a delivery failure from later records", async () => {
    const attempted: string[] = [];

    const fetchImpl: typeof fetch = async (_input, init) => {
      const body = JSON.parse(String(init?.body ?? "{}"));

      const eventId = String(body.event_id);

      attempted.push(eventId);

      if (eventId === "7c1f9d0a-f544-47b3-b1df-642875a8fa49") {
        return new Response(null, {
          status: 503,
        });
      }

      return new Response(null, {
        status: 204,
      });
    };

    const result = await handleWebhookBatch(
      event([
        sqsRecord(
          "message-failed",
          JSON.stringify(notification("7c1f9d0a-f544-47b3-b1df-642875a8fa49")),
        ),

        sqsRecord(
          "message-success",
          JSON.stringify(notification("29c43085-9e80-4df6-bef7-09d24ca97570")),
        ),
      ]),
      dependencies(fetchImpl),
    );

    expect(result).toEqual({
      batchItemFailures: [
        {
          itemIdentifier: "message-failed",
        },
      ],
    });

    expect(attempted).toEqual([
      "7c1f9d0a-f544-47b3-b1df-642875a8fa49",
      "29c43085-9e80-4df6-bef7-09d24ca97570",
    ]);
  });

  it("returns malformed JSON as a failed record and continues", async () => {
    const delivered: string[] = [];

    const fetchImpl: typeof fetch = async (_input, init) => {
      const body = JSON.parse(String(init?.body ?? "{}"));

      delivered.push(String(body.event_id));

      return new Response(null, {
        status: 200,
      });
    };

    const result = await handleWebhookBatch(
      event([
        sqsRecord("message-invalid-json", "{this-is-not-json"),

        sqsRecord(
          "message-valid",
          JSON.stringify(notification("29c43085-9e80-4df6-bef7-09d24ca97570")),
        ),
      ]),
      dependencies(fetchImpl),
    );

    expect(result).toEqual({
      batchItemFailures: [
        {
          itemIdentifier: "message-invalid-json",
        },
      ],
    });

    expect(delivered).toEqual(["29c43085-9e80-4df6-bef7-09d24ca97570"]);
  });

  it("returns contract-invalid notifications as failed records", async () => {
    let fetchCalls = 0;

    const fetchImpl: typeof fetch = async () => {
      fetchCalls += 1;

      return new Response(null, {
        status: 204,
      });
    };

    const invalid = {
      ...notification("7c1f9d0a-f544-47b3-b1df-642875a8fa49"),

      type: "incident.created",
    };

    const result = await handleWebhookBatch(
      event([sqsRecord("message-invalid-contract", JSON.stringify(invalid))]),
      dependencies(fetchImpl),
    );

    expect(result).toEqual({
      batchItemFailures: [
        {
          itemIdentifier: "message-invalid-contract",
        },
      ],
    });

    expect(fetchCalls).toBe(0);
  });

  it("returns non-retryable HTTP failures as failed SQS records", async () => {
    const fetchImpl: typeof fetch = async () =>
      new Response(null, {
        status: 400,
      });

    const result = await handleWebhookBatch(
      event([
        sqsRecord(
          "message-http-400",
          JSON.stringify(notification("7c1f9d0a-f544-47b3-b1df-642875a8fa49")),
        ),
      ]),
      dependencies(fetchImpl),
    );

    expect(result).toEqual({
      batchItemFailures: [
        {
          itemIdentifier: "message-http-400",
        },
      ],
    });
  });

  it("preserves event identity but refreshes the signature timestamp on retry", async () => {
    const captured: {
      eventId: string;

      body: string;

      timestamp: string | null;

      signature: string | null;
    }[] = [];

    const fetchImpl: typeof fetch = async (_input, init) => {
      const headers = new Headers(init?.headers);

      const body = String(init?.body ?? "");

      const parsed = JSON.parse(body);

      captured.push({
        eventId: String(parsed.event_id),

        body,

        timestamp: headers.get("x-opsflow-webhook-timestamp"),

        signature: headers.get("x-opsflow-webhook-signature"),
      });

      return new Response(null, {
        status: 204,
      });
    };

    const timestamps = [1790085600, 1790085601];

    let clockIndex = 0;

    const nowSeconds = () => {
      const value = timestamps[clockIndex];

      clockIndex += 1;

      if (value === undefined) {
        throw new Error("Synthetic clock exhausted.");
      }

      return value;
    };

    const record = sqsRecord(
      "message-retried",
      JSON.stringify(notification("7c1f9d0a-f544-47b3-b1df-642875a8fa49")),
    );

    await handleWebhookBatch(
      event([record]),
      dependencies(fetchImpl, nowSeconds),
    );

    await handleWebhookBatch(
      event([record]),
      dependencies(fetchImpl, nowSeconds),
    );

    expect(captured).toHaveLength(2);

    expect(captured[0]?.eventId).toBe("7c1f9d0a-f544-47b3-b1df-642875a8fa49");

    expect(captured[1]?.eventId).toBe(captured[0]?.eventId);

    expect(captured[1]?.body).toBe(captured[0]?.body);

    expect(captured[0]?.timestamp).toBe("1790085600");

    expect(captured[1]?.timestamp).toBe("1790085601");

    expect(captured[1]?.signature).not.toBe(captured[0]?.signature);
  });
});
