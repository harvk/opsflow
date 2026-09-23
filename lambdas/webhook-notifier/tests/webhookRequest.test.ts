import { describe, expect, it } from "vitest";

import { verifyWebhookSignature } from "../src/webhookSignature";

import {
  InvalidWebhookTargetError,
  buildWebhookRequest,
} from "../src/webhookRequest";

import type { IncidentUpdatedNotification } from "../src/types";

const SECRET = "opsflow-test-webhook-secret-0123456789abcdef";

const TIMESTAMP = 1790085600;

function notification(): IncidentUpdatedNotification {
  return {
    type: "incident.updated",

    schema_version: "1.0",

    event_id: "7c1f9d0a-f544-47b3-b1df-642875a8fa49",

    incident_id: "aca0a505-b460-4d08-9035-3b92bac0fff1",

    task_id: "bb587a5f-3c94-4e03-8b13-159d8f58acfa",

    correlation_id: "phase-11-5g-4f2",

    status: "Investigating",

    acknowledged_at: "2026-09-22T14:00:00Z",

    occurred_at: "2026-09-22T14:00:01Z",
  };
}

describe("buildWebhookRequest", () => {
  it("creates an HTTPS POST request", () => {
    const value = notification();

    const request = buildWebhookRequest(
      value,
      {
        url: "https://example.com/hooks/incidents",
      },
      {
        secret: SECRET,

        timestampSeconds: TIMESTAMP,
      },
    );

    expect(request.method).toBe("POST");

    expect(request.url).toBe("https://example.com/hooks/incidents");

    expect(JSON.parse(request.body)).toEqual(value);
  });

  it("includes stable notification identity headers", () => {
    const value = notification();

    const request = buildWebhookRequest(
      value,
      {
        url: "https://example.com/hooks/incidents",
      },
      {
        secret: SECRET,

        timestampSeconds: TIMESTAMP,
      },
    );

    expect(request.headers["content-type"]).toBe("application/json");

    expect(request.headers["user-agent"]).toBe("OpsFlow-Webhook/1.0");

    expect(request.headers["x-opsflow-event-id"]).toBe(value.event_id);

    expect(request.headers["x-opsflow-event-type"]).toBe("incident.updated");

    expect(request.headers["x-opsflow-schema-version"]).toBe("1.0");
  });

  it("includes timestamp and HMAC signature headers", () => {
    const request = buildWebhookRequest(
      notification(),
      {
        url: "https://example.com/hooks/incidents",
      },
      {
        secret: SECRET,

        timestampSeconds: TIMESTAMP,
      },
    );

    expect(request.headers["x-opsflow-webhook-timestamp"]).toBe(
      String(TIMESTAMP),
    );

    expect(request.headers["x-opsflow-webhook-signature"]).toMatch(
      /^v1=[0-9a-f]{64}$/u,
    );
  });

  it("signs the exact HTTP body", () => {
    const request = buildWebhookRequest(
      notification(),
      {
        url: "https://example.com/hooks/incidents",
      },
      {
        secret: SECRET,

        timestampSeconds: TIMESTAMP,
      },
    );

    const signature = request.headers["x-opsflow-webhook-signature"];

    expect(
      verifyWebhookSignature({
        body: request.body,

        timestampSeconds: TIMESTAMP,

        secret: SECRET,

        signatureHeader: signature,

        currentTimestampSeconds: TIMESTAMP,

        toleranceSeconds: 300,
      }),
    ).toBe(true);
  });

  it("produces the same signed request for identical inputs", () => {
    const value = notification();

    const target = {
      url: "https://example.com/hooks/incidents",
    };

    const signing = {
      secret: SECRET,

      timestampSeconds: TIMESTAMP,
    };

    const first = buildWebhookRequest(value, target, signing);

    const second = buildWebhookRequest(value, target, signing);

    expect(second).toEqual(first);
  });

  it("changes the signature when the timestamp changes", () => {
    const value = notification();

    const first = buildWebhookRequest(
      value,
      {
        url: "https://example.com/hooks/incidents",
      },
      {
        secret: SECRET,

        timestampSeconds: TIMESTAMP,
      },
    );

    const second = buildWebhookRequest(
      value,
      {
        url: "https://example.com/hooks/incidents",
      },
      {
        secret: SECRET,

        timestampSeconds: TIMESTAMP + 1,
      },
    );

    expect(second.headers["x-opsflow-webhook-signature"]).not.toBe(
      first.headers["x-opsflow-webhook-signature"],
    );
  });

  it("rejects non-HTTPS targets", () => {
    expect(() =>
      buildWebhookRequest(
        notification(),
        {
          url: "http://example.com/hooks/incidents",
        },
        {
          secret: SECRET,

          timestampSeconds: TIMESTAMP,
        },
      ),
    ).toThrow(InvalidWebhookTargetError);
  });

  it("rejects embedded URL credentials", () => {
    expect(() =>
      buildWebhookRequest(
        notification(),
        {
          url: "https://user:secret@example.com/hooks",
        },
        {
          secret: SECRET,

          timestampSeconds: TIMESTAMP,
        },
      ),
    ).toThrow(InvalidWebhookTargetError);
  });

  it("rejects invalid absolute URLs", () => {
    expect(() =>
      buildWebhookRequest(
        notification(),
        {
          url: "not-a-url",
        },
        {
          secret: SECRET,

          timestampSeconds: TIMESTAMP,
        },
      ),
    ).toThrow(InvalidWebhookTargetError);
  });

  it("does not mutate the source notification", () => {
    const value = notification();

    const before = JSON.stringify(value);

    buildWebhookRequest(
      value,
      {
        url: "https://example.com/hooks/incidents",
      },
      {
        secret: SECRET,

        timestampSeconds: TIMESTAMP,
      },
    );

    expect(JSON.stringify(value)).toBe(before);
  });
});
