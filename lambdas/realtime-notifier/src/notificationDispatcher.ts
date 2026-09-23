import {
  broadcastIncidentTaskCompletedEvent,
  buildRealtimeIncidentMessage,
} from "./notifier";

import { validateRealtimeIncidentMessage } from "./notificationContract";

import { enqueueWebhookNotification } from "./webhookHandoff";

import type {
  IncidentTaskCompletedEvent,
  RealtimeIncidentMessage,
} from "./types";

export type NotificationDispatchChannel = "websocket" | "webhook";

export interface NotificationDispatchFailure {
  channel: NotificationDispatchChannel;

  errorType: string;

  message: string;
}

export interface NotificationDispatcherDependencies {
  broadcastNotification: (event: IncidentTaskCompletedEvent) => Promise<void>;

  enqueueWebhookNotification: (
    notification: RealtimeIncidentMessage,
  ) => Promise<void>;
}

export class NotificationDispatchError extends Error {
  readonly eventId: string;

  readonly failures: readonly NotificationDispatchFailure[];

  constructor(
    eventId: string,

    failures: readonly NotificationDispatchFailure[],
  ) {
    const channels = failures.map((failure) => failure.channel).join(", ");

    super(
      "Notification dispatch failed " +
        `for event ${eventId} ` +
        `on channel(s): ${channels}`,
    );

    this.name = "NotificationDispatchError";

    this.eventId = eventId;

    this.failures = [...failures];
  }
}

const defaultDependencies: NotificationDispatcherDependencies = {
  broadcastNotification: broadcastIncidentTaskCompletedEvent,

  enqueueWebhookNotification,
};

function describeError(error: unknown): {
  errorType: string;

  message: string;
} {
  if (error instanceof Error) {
    return {
      errorType: error.name,

      message: error.message,
    };
  }

  return {
    errorType: "UnknownError",

    message: "Unknown notification dispatch error",
  };
}

export async function dispatchIncidentTaskCompletedEvent(
  event: IncidentTaskCompletedEvent,

  dependencies: NotificationDispatcherDependencies = defaultDependencies,
): Promise<void> {
  /*
   * Construct and validate the public notification before
   * starting either delivery-side effect.
   */

  const publicNotification = validateRealtimeIncidentMessage(
    buildRealtimeIncidentMessage(event),
  );

  /*
   * Start both delivery paths independently.
   *
   * Promise.allSettled is intentional:
   *
   * - WebSocket failure must not prevent webhook handoff.
   * - Webhook queue failure must not prevent WebSocket
   *   delivery.
   *
   * After both operations finish, any failures are
   * aggregated so the original source SQS record remains
   * failed and can be retried.
   */

  const [websocketResult, webhookResult] = await Promise.allSettled([
    dependencies.broadcastNotification(event),

    dependencies.enqueueWebhookNotification(publicNotification),
  ]);

  const failures: NotificationDispatchFailure[] = [];

  if (websocketResult.status === "rejected") {
    const details = describeError(websocketResult.reason);

    failures.push({
      channel: "websocket",

      errorType: details.errorType,

      message: details.message,
    });
  }

  if (webhookResult.status === "rejected") {
    const details = describeError(webhookResult.reason);

    failures.push({
      channel: "webhook",

      errorType: details.errorType,

      message: details.message,
    });
  }

  if (failures.length > 0) {
    throw new NotificationDispatchError(publicNotification.event_id, failures);
  }
}
