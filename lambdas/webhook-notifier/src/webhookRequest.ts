import { createWebhookSignature } from "./webhookSignature";

import type {
  IncidentUpdatedNotification,
  WebhookDeliveryTarget,
  WebhookHttpRequest,
} from "./types";

const WEBHOOK_USER_AGENT = "OpsFlow-Webhook/1.0";

export interface WebhookRequestSigningOptions {
  secret: string;

  timestampSeconds: number;
}

export class InvalidWebhookTargetError extends Error {
  constructor(message: string) {
    super(message);

    this.name = "InvalidWebhookTargetError";
  }
}

function validateTargetUrl(value: string): string {
  const normalized = value.trim();

  if (normalized.length === 0) {
    throw new InvalidWebhookTargetError(
      "Webhook target URL must not be empty.",
    );
  }

  let parsed: URL;

  try {
    parsed = new URL(normalized);
  } catch {
    throw new InvalidWebhookTargetError(
      "Webhook target URL must be a valid absolute URL.",
    );
  }

  if (parsed.protocol !== "https:") {
    throw new InvalidWebhookTargetError("Webhook target URL must use HTTPS.");
  }

  if (parsed.username.length > 0 || parsed.password.length > 0) {
    throw new InvalidWebhookTargetError(
      "Webhook target URL must not contain " + "embedded credentials.",
    );
  }

  return parsed.toString();
}

export function buildWebhookRequest(
  notification: IncidentUpdatedNotification,

  target: WebhookDeliveryTarget,

  signing: WebhookRequestSigningOptions,
): WebhookHttpRequest {
  const url = validateTargetUrl(target.url);

  /*
   * The body is created exactly once.
   *
   * This exact string is both:
   *
   *   1. signed; and
   *   2. sent over HTTP.
   *
   * Receivers must verify the signature against the raw
   * body bytes they received rather than parsing and
   * reserializing the JSON first.
   */

  const body = JSON.stringify(notification);

  const signature = createWebhookSignature({
    body,

    timestampSeconds: signing.timestampSeconds,

    secret: signing.secret,
  });

  return {
    method: "POST",

    url,

    headers: {
      "content-type": "application/json",

      "user-agent": WEBHOOK_USER_AGENT,

      "x-opsflow-event-id": notification.event_id,

      "x-opsflow-event-type": notification.type,

      "x-opsflow-schema-version": notification.schema_version,

      "x-opsflow-webhook-timestamp": String(signing.timestampSeconds),

      "x-opsflow-webhook-signature": signature,
    },

    body,
  };
}
