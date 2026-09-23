import type { SQSBatchResponse, SQSEvent, SQSRecord } from "aws-lambda";

import { loadWebhookRuntimeConfig } from "./config";

import { sendWebhookRequest } from "./httpClient";

import { validateWebhookNotification } from "./notificationContract";

import { buildWebhookRequest } from "./webhookRequest";

import type { WebhookRuntimeConfig } from "./config";

import type { WebhookDeliveryTarget } from "./types";

export interface WebhookBatchDependencies {
  target: WebhookDeliveryTarget;

  signingSecret: string;

  timeoutMs: number;

  nowSeconds: () => number;

  fetchImpl?: typeof fetch;
}

export interface WebhookProductionDependencies {
  loadConfig: () => Promise<WebhookRuntimeConfig>;

  nowSeconds: () => number;

  fetchImpl?: typeof fetch;
}

const defaultProductionDependencies: WebhookProductionDependencies = {
  loadConfig: loadWebhookRuntimeConfig,

  nowSeconds: () => Math.floor(Date.now() / 1000),
};

async function processRecord(
  record: SQSRecord,

  dependencies: WebhookBatchDependencies,
): Promise<void> {
  const parsed = JSON.parse(record.body) as unknown;

  const notification = validateWebhookNotification(parsed);

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

  for (const record of event.Records) {
    try {
      await processRecord(record, dependencies);

      console.log(
        JSON.stringify({
          level: "info",

          event: "webhook_notification_delivered",

          sqs_message_id: record.messageId,
        }),
      );
    } catch (error) {
      console.error(
        JSON.stringify({
          level: "error",

          event: "webhook_notification_delivery_failed",

          sqs_message_id: record.messageId,

          error_type: error instanceof Error ? error.name : "UnknownError",

          error:
            error instanceof Error
              ? error.message
              : "Unknown webhook delivery error",
        }),
      );

      batchItemFailures.push({
        itemIdentifier: record.messageId,
      });
    }
  }

  return {
    batchItemFailures,
  };
}

export function createHandler(
  dependencies: WebhookProductionDependencies = defaultProductionDependencies,
) {
  let cachedConfigPromise: Promise<WebhookRuntimeConfig> | undefined;

  async function getConfig(): Promise<WebhookRuntimeConfig> {
    if (cachedConfigPromise === undefined) {
      cachedConfigPromise = dependencies.loadConfig();
    }

    try {
      return await cachedConfigPromise;
    } catch (error) {
      /*
       * Do not permanently poison a warm Lambda execution
       * environment after a transient Secrets Manager or
       * configuration retrieval failure.
       */
      cachedConfigPromise = undefined;

      throw error;
    }
  }

  return async function handler(event: SQSEvent): Promise<SQSBatchResponse> {
    const config = await getConfig();

    return handleWebhookBatch(event, {
      target: {
        url: config.targetUrl,
      },

      signingSecret: config.signingSecret,

      timeoutMs: config.timeoutMs,

      nowSeconds: dependencies.nowSeconds,

      fetchImpl: dependencies.fetchImpl,
    });
  };
}

export const handler = createHandler();
