import { describe, expect, it } from "vitest";

import {
  InvalidWebhookSigningSecretError,
  InvalidWebhookTimestampError,
  createWebhookSignature,
  verifyWebhookSignature,
} from "../src/webhookSignature";

const SECRET = "opsflow-test-webhook-secret-0123456789abcdef";

const TIMESTAMP = 1790085600;

const BODY = JSON.stringify({
  type: "incident.updated",

  schema_version: "1.0",

  event_id: "7c1f9d0a-f544-47b3-b1df-642875a8fa49",

  status: "Investigating",
});

describe("webhook HMAC signatures", () => {
  it("creates deterministic signatures", () => {
    const first = createWebhookSignature({
      body: BODY,

      timestampSeconds: TIMESTAMP,

      secret: SECRET,
    });

    const second = createWebhookSignature({
      body: BODY,

      timestampSeconds: TIMESTAMP,

      secret: SECRET,
    });

    expect(first).toBe(second);

    expect(first).toMatch(/^v1=[0-9a-f]{64}$/u);
  });

  it("verifies an authentic signature", () => {
    const signature = createWebhookSignature({
      body: BODY,

      timestampSeconds: TIMESTAMP,

      secret: SECRET,
    });

    expect(
      verifyWebhookSignature({
        body: BODY,

        timestampSeconds: TIMESTAMP,

        secret: SECRET,

        signatureHeader: signature,

        currentTimestampSeconds: TIMESTAMP,

        toleranceSeconds: 300,
      }),
    ).toBe(true);
  });

  it("rejects a tampered body", () => {
    const signature = createWebhookSignature({
      body: BODY,

      timestampSeconds: TIMESTAMP,

      secret: SECRET,
    });

    expect(
      verifyWebhookSignature({
        body: `${BODY} `,

        timestampSeconds: TIMESTAMP,

        secret: SECRET,

        signatureHeader: signature,

        currentTimestampSeconds: TIMESTAMP,

        toleranceSeconds: 300,
      }),
    ).toBe(false);
  });

  it("rejects a different secret", () => {
    const signature = createWebhookSignature({
      body: BODY,

      timestampSeconds: TIMESTAMP,

      secret: SECRET,
    });

    expect(
      verifyWebhookSignature({
        body: BODY,

        timestampSeconds: TIMESTAMP,

        secret: "different-webhook-secret-0123456789abcdef",

        signatureHeader: signature,

        currentTimestampSeconds: TIMESTAMP,

        toleranceSeconds: 300,
      }),
    ).toBe(false);
  });

  it("rejects a modified timestamp", () => {
    const signature = createWebhookSignature({
      body: BODY,

      timestampSeconds: TIMESTAMP,

      secret: SECRET,
    });

    expect(
      verifyWebhookSignature({
        body: BODY,

        timestampSeconds: TIMESTAMP + 1,

        secret: SECRET,

        signatureHeader: signature,

        currentTimestampSeconds: TIMESTAMP + 1,

        toleranceSeconds: 300,
      }),
    ).toBe(false);
  });

  it("rejects signatures outside the replay tolerance", () => {
    const signature = createWebhookSignature({
      body: BODY,

      timestampSeconds: TIMESTAMP,

      secret: SECRET,
    });

    expect(
      verifyWebhookSignature({
        body: BODY,

        timestampSeconds: TIMESTAMP,

        secret: SECRET,

        signatureHeader: signature,

        currentTimestampSeconds: TIMESTAMP + 301,

        toleranceSeconds: 300,
      }),
    ).toBe(false);
  });

  it("accepts a signature exactly at the replay tolerance boundary", () => {
    const signature = createWebhookSignature({
      body: BODY,

      timestampSeconds: TIMESTAMP,

      secret: SECRET,
    });

    expect(
      verifyWebhookSignature({
        body: BODY,

        timestampSeconds: TIMESTAMP,

        secret: SECRET,

        signatureHeader: signature,

        currentTimestampSeconds: TIMESTAMP + 300,

        toleranceSeconds: 300,
      }),
    ).toBe(true);
  });

  it("rejects an unsupported signature version", () => {
    const signature = createWebhookSignature({
      body: BODY,

      timestampSeconds: TIMESTAMP,

      secret: SECRET,
    });

    const unsupported = signature.replace(/^v1=/u, "v2=");

    expect(
      verifyWebhookSignature({
        body: BODY,

        timestampSeconds: TIMESTAMP,

        secret: SECRET,

        signatureHeader: unsupported,

        currentTimestampSeconds: TIMESTAMP,

        toleranceSeconds: 300,
      }),
    ).toBe(false);
  });

  it("rejects malformed signature digests", () => {
    expect(
      verifyWebhookSignature({
        body: BODY,

        timestampSeconds: TIMESTAMP,

        secret: SECRET,

        signatureHeader: "v1=not-a-sha256-digest",

        currentTimestampSeconds: TIMESTAMP,

        toleranceSeconds: 300,
      }),
    ).toBe(false);
  });

  it("rejects secrets shorter than 32 bytes", () => {
    expect(() =>
      createWebhookSignature({
        body: BODY,

        timestampSeconds: TIMESTAMP,

        secret: "too-short",
      }),
    ).toThrow(InvalidWebhookSigningSecretError);
  });

  it("rejects invalid timestamps", () => {
    expect(() =>
      createWebhookSignature({
        body: BODY,

        timestampSeconds: 0,

        secret: SECRET,
      }),
    ).toThrow(InvalidWebhookTimestampError);
  });
});
