import type { WebhookHttpRequest } from "./types";

const MAXIMUM_TIMEOUT_MS = 30_000;

export type WebhookDeliveryFailureKind = "http" | "network" | "timeout";

export interface WebhookHttpClientOptions {
  timeoutMs: number;

  fetchImpl?: typeof fetch;
}

export interface WebhookHttpStatusClassification {
  success: boolean;

  retryable: boolean;
}

export class InvalidWebhookHttpTimeoutError extends Error {
  constructor(message: string) {
    super(message);

    this.name = "InvalidWebhookHttpTimeoutError";
  }
}

export class WebhookDeliveryError extends Error {
  readonly kind: WebhookDeliveryFailureKind;

  readonly retryable: boolean;

  readonly statusCode: number | null;

  constructor(options: {
    message: string;

    kind: WebhookDeliveryFailureKind;

    retryable: boolean;

    statusCode?: number | null;
  }) {
    super(options.message);

    this.name = "WebhookDeliveryError";

    this.kind = options.kind;

    this.retryable = options.retryable;

    this.statusCode = options.statusCode ?? null;
  }
}

function validateTimeout(timeoutMs: number): void {
  if (
    !Number.isSafeInteger(timeoutMs) ||
    timeoutMs <= 0 ||
    timeoutMs > MAXIMUM_TIMEOUT_MS
  ) {
    throw new InvalidWebhookHttpTimeoutError(
      "Webhook HTTP timeout must be a " +
        "positive safe integer no greater " +
        `than ${MAXIMUM_TIMEOUT_MS} milliseconds.`,
    );
  }
}

export function classifyWebhookHttpStatus(
  statusCode: number,
): WebhookHttpStatusClassification {
  if (statusCode >= 200 && statusCode <= 299) {
    return {
      success: true,

      retryable: false,
    };
  }

  const retryable =
    statusCode === 408 ||
    statusCode === 425 ||
    statusCode === 429 ||
    (statusCode >= 500 && statusCode <= 599);

  return {
    success: false,

    retryable,
  };
}

export async function sendWebhookRequest(
  request: WebhookHttpRequest,

  options: WebhookHttpClientOptions,
): Promise<void> {
  validateTimeout(options.timeoutMs);

  const fetchImpl = options.fetchImpl ?? fetch;

  const controller = new AbortController();

  const timeout = setTimeout(() => {
    controller.abort();
  }, options.timeoutMs);

  try {
    /*
     * Redirect handling is intentionally manual.
     *
     * OpsFlow must never automatically forward the signed
     * webhook request, including its HMAC signature, to a
     * different host returned by a redirect response.
     */

    const response = await fetchImpl(request.url, {
      method: request.method,

      headers: request.headers,

      body: request.body,

      signal: controller.signal,

      redirect: "manual",
    });

    const classification = classifyWebhookHttpStatus(response.status);

    if (classification.success) {
      return;
    }

    throw new WebhookDeliveryError({
      message: "Webhook endpoint returned " + `HTTP ${response.status}.`,

      kind: "http",

      retryable: classification.retryable,

      statusCode: response.status,
    });
  } catch (error) {
    if (error instanceof WebhookDeliveryError) {
      throw error;
    }

    if (controller.signal.aborted) {
      throw new WebhookDeliveryError({
        message:
          "Webhook delivery exceeded " + `the ${options.timeoutMs}ms timeout.`,

        kind: "timeout",

        retryable: true,
      });
    }

    throw new WebhookDeliveryError({
      message: "Webhook network request failed.",

      kind: "network",

      retryable: true,
    });
  } finally {
    clearTimeout(timeout);
  }
}
