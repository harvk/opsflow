import type {
  IncidentUpdatedNotification,
  WebhookDeliveryTarget,
  WebhookHttpRequest,
} from "./types";

const WEBHOOK_USER_AGENT = "OpsFlow-Webhook/1.0";

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
      "Webhook target URL must not contain embedded credentials.",
    );
  }

  return parsed.toString();
}

export function buildWebhookRequest(
  notification: IncidentUpdatedNotification,

  target: WebhookDeliveryTarget,
): WebhookHttpRequest {
  const url = validateTargetUrl(target.url);

  const body = JSON.stringify(notification);

  return {
    method: "POST",

    url,

    headers: {
      "content-type": "application/json",

      "user-agent": WEBHOOK_USER_AGENT,

      "x-opsflow-event-id": notification.event_id,

      "x-opsflow-event-type": notification.type,

      "x-opsflow-schema-version": notification.schema_version,
    },

    body,
  };
}
