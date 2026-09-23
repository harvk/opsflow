import { SendMessageCommand, SQSClient } from "@aws-sdk/client-sqs";

import { validateRealtimeIncidentMessage } from "./notificationContract";

import type { RealtimeIncidentMessage } from "./types";

const WEBHOOK_NOTIFICATION_QUEUE_URL_ENV = "WEBHOOK_NOTIFICATION_QUEUE_URL";

export interface WebhookHandoffDependencies {
  queueUrl: string;

  sendMessage: (
    queueUrl: string,

    body: string,
  ) => Promise<void>;
}

export class WebhookHandoffConfigurationError extends Error {
  constructor(message: string) {
    super(message);

    this.name = "WebhookHandoffConfigurationError";
  }
}

const sqsClient = new SQSClient({});

function requireWebhookNotificationQueueUrl(): string {
  const value = process.env[WEBHOOK_NOTIFICATION_QUEUE_URL_ENV]?.trim();

  if (value === undefined || value.length === 0) {
    throw new WebhookHandoffConfigurationError(
      `${WEBHOOK_NOTIFICATION_QUEUE_URL_ENV} ` + "must be configured.",
    );
  }

  return value;
}

async function sendMessage(
  queueUrl: string,

  body: string,
): Promise<void> {
  await sqsClient.send(
    new SendMessageCommand({
      QueueUrl: queueUrl,

      MessageBody: body,
    }),
  );
}

function createDefaultDependencies(): WebhookHandoffDependencies {
  /*
   * Resolve the queue URL lazily.
   *
   * Unit tests that inject dependencies must not require
   * production Lambda environment configuration merely by
   * importing this module.
   */

  return {
    queueUrl: requireWebhookNotificationQueueUrl(),

    sendMessage,
  };
}

export async function enqueueWebhookNotification(
  notification: RealtimeIncidentMessage,

  dependencies?: WebhookHandoffDependencies,
): Promise<void> {
  const resolvedDependencies = dependencies ?? createDefaultDependencies();

  /*
   * Validate the public contract immediately before the
   * durable handoff.
   *
   * This is defense in depth. The dispatcher constructs
   * this same contract, but the queue boundary must never
   * accept an invalid incident.updated payload.
   */

  const validated = validateRealtimeIncidentMessage(notification);

  const body = JSON.stringify(validated);

  await resolvedDependencies.sendMessage(
    resolvedDependencies.queueUrl,

    body,
  );
}
