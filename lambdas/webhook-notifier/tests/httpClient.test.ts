import { describe, expect, it } from "vitest";

import {
  InvalidWebhookHttpTimeoutError,
  WebhookDeliveryError,
  classifyWebhookHttpStatus,
  sendWebhookRequest,
} from "../src/httpClient";

import type { WebhookHttpRequest } from "../src/types";

function request(): WebhookHttpRequest {
  return {
    method: "POST",

    url: "https://example.com/hooks/incidents",

    headers: {
      "content-type": "application/json",

      "x-opsflow-webhook-signature": "v1=test-signature",
    },

    body: '{"type":"incident.updated"}',
  };
}

function fetchReturning(status: number): typeof fetch {
  return async () =>
    new Response(null, {
      status,
    });
}

describe("classifyWebhookHttpStatus", () => {
  it.each([200, 201, 202, 204, 299])(
    "treats HTTP %i as successful",
    (status) => {
      expect(classifyWebhookHttpStatus(status)).toEqual({
        success: true,

        retryable: false,
      });
    },
  );

  it.each([408, 425, 429, 500, 502, 503, 504, 599])(
    "treats HTTP %i as retryable",
    (status) => {
      expect(classifyWebhookHttpStatus(status)).toEqual({
        success: false,

        retryable: true,
      });
    },
  );

  it.each([300, 301, 302, 307, 308, 400, 401, 403, 404, 409, 410, 422])(
    "treats HTTP %i as non-retryable",
    (status) => {
      expect(classifyWebhookHttpStatus(status)).toEqual({
        success: false,

        retryable: false,
      });
    },
  );
});

describe("sendWebhookRequest", () => {
  it("accepts successful 2xx responses", async () => {
    await expect(
      sendWebhookRequest(request(), {
        timeoutMs: 5_000,

        fetchImpl: fetchReturning(204),
      }),
    ).resolves.toBeUndefined();
  });

  it("reports retryable HTTP failures", async () => {
    try {
      await sendWebhookRequest(request(), {
        timeoutMs: 5_000,

        fetchImpl: fetchReturning(503),
      });

      throw new Error("Expected webhook request to fail.");
    } catch (error) {
      expect(error).toBeInstanceOf(WebhookDeliveryError);

      if (!(error instanceof WebhookDeliveryError)) {
        throw error;
      }

      expect(error.kind).toBe("http");

      expect(error.statusCode).toBe(503);

      expect(error.retryable).toBe(true);
    }
  });

  it("reports non-retryable HTTP failures", async () => {
    try {
      await sendWebhookRequest(request(), {
        timeoutMs: 5_000,

        fetchImpl: fetchReturning(400),
      });

      throw new Error("Expected webhook request to fail.");
    } catch (error) {
      expect(error).toBeInstanceOf(WebhookDeliveryError);

      if (!(error instanceof WebhookDeliveryError)) {
        throw error;
      }

      expect(error.kind).toBe("http");

      expect(error.statusCode).toBe(400);

      expect(error.retryable).toBe(false);
    }
  });

  it("does not automatically follow redirects", async () => {
    let calls = 0;

    const fetchImpl: typeof fetch = async (_input, init) => {
      calls += 1;

      expect(init?.redirect).toBe("manual");

      return new Response(null, {
        status: 302,

        headers: {
          location: "https://different.example.com/webhook",
        },
      });
    };

    await expect(
      sendWebhookRequest(request(), {
        timeoutMs: 5_000,

        fetchImpl,
      }),
    ).rejects.toMatchObject({
      kind: "http",

      retryable: false,

      statusCode: 302,
    });

    expect(calls).toBe(1);
  });

  it("classifies network failures as retryable", async () => {
    const fetchImpl: typeof fetch = async () => {
      throw new TypeError("synthetic network failure");
    };

    await expect(
      sendWebhookRequest(request(), {
        timeoutMs: 5_000,

        fetchImpl,
      }),
    ).rejects.toMatchObject({
      kind: "network",

      retryable: true,

      statusCode: null,
    });
  });

  it("aborts requests that exceed the configured timeout", async () => {
    const fetchImpl: typeof fetch = async (_input, init) =>
      await new Promise((_resolve, reject) => {
        const signal = init?.signal;

        if (signal === null || signal === undefined) {
          reject(new Error("Expected AbortSignal."));

          return;
        }

        signal.addEventListener(
          "abort",
          () => {
            reject(
              new DOMException("The operation was aborted.", "AbortError"),
            );
          },
          {
            once: true,
          },
        );
      });

    await expect(
      sendWebhookRequest(request(), {
        timeoutMs: 10,

        fetchImpl,
      }),
    ).rejects.toMatchObject({
      kind: "timeout",

      retryable: true,

      statusCode: null,
    });
  });

  it.each([0, -1, 30_001, 1.5, Number.NaN])(
    "rejects invalid timeout value %s",
    async (timeoutMs) => {
      await expect(
        sendWebhookRequest(request(), {
          timeoutMs,

          fetchImpl: fetchReturning(204),
        }),
      ).rejects.toBeInstanceOf(InvalidWebhookHttpTimeoutError);
    },
  );
});
