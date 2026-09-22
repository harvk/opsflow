import type { SQSBatchResponse, SQSEvent, SQSRecord } from "aws-lambda";

import { sendWebhookRequest } from "./httpClient";

import { validateWebhookNotification } from "./notificationContract";

import { buildWebhookRequest } from "./webhookRequest";

import type { WebhookDeliveryTarget } from "./types";

export interface WebhookBatchDependencies {
  target: WebhookDeliveryTarget;

  signingSecret: string;

  timeoutMs: number;

  nowSeconds: () => number;

  fetchImpl?: typeof fetch;
}

async function processRecord(
  record: SQSRecord,

  dependencies: WebhookBatchDependencies,
): Promise<void> {
  /*
   * The dedicated webhook queue carries the public
   * incident.updated notification contract directly.
   *
   * Validation therefore occurs before signing and before
   * any HTTP-side effect.
   */

  const parsed = JSON.parse(record.body) as unknown;

  const notification = validateWebhookNotification(parsed);

  /*
   * A new signature timestamp is generated for each
   * delivery attempt.
   *
   * SQS retries preserve event_id and body identity while
   * receiving a fresh HMAC timestamp/signature, preventing
   * normal retries from being rejected by a short receiver
   * replay window.
   */

  const timestampSeconds = dependencies.nowSeconds();

  const request = buildWebhookRequest(notification, dependencies.target, {
    secret: dependencies.signingSecret,

    timestampSeconds,
  });

  await sendWebhookRequest(request, {
    timeoutMs: dependencies.timeoutMs,

    fetchImpl: dependencies.fetchImpl,
  });
}

export async function handleWebhookBatch(
  event: SQSEvent,

  dependencies: WebhookBatchDependencies,
): Promise<SQSBatchResponse> {
  const batchItemFailures: SQSBatchResponse["batchItemFailures"] = [];

  /*
   * Process each SQS record independently.
   *
   * A malformed contract, HTTP error, timeout, or network
   * failure must not prevent later records in the same batch
   * from being attempted.
   */

  for (const record of event.Records) {
    try {
      await processRecord(record, dependencies);
    } catch {
      /*
       * Both retryable and non-retryable delivery failures
       * remain failed records.
       *
       * The future dedicated queue redrive policy will move
       * repeatedly failing records to the webhook DLQ rather
       * than silently discarding them.
       */

      batchItemFailures.push({
        itemIdentifier: record.messageId,
      });
    }
  }

  return {
    batchItemFailures,
  };
}
