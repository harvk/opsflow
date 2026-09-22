import {
  describe,
  expect,
  it,
} from "vitest";

import {
  WebhookNotifierConfigurationError,
  loadWebhookRuntimeConfig,
} from "../src/config";

const SIGNING_SECRET =
  "opsflow-test-webhook-secret-0123456789abcdef";

function environment(
  overrides:
    NodeJS.ProcessEnv = {},
): NodeJS.ProcessEnv {
  return {
    WEBHOOK_CONFIG_SECRET_ARN:
      "arn:aws:secretsmanager:us-east-1:"
      + "123456789012:secret:opsflow-dev-webhook-notifier-config",

    WEBHOOK_HTTP_TIMEOUT_MS:
      "5000",

    ...overrides,
  };
}

function secretPayload(
  overrides:
    Record<string, unknown> = {},
): string {
  return JSON.stringify({
    target_url:
      "https://example.com/hooks/incidents",

    signing_secret:
      SIGNING_SECRET,

    ...overrides,
  });
}

describe(
  "loadWebhookRuntimeConfig",
  () => {
    it(
      "loads target, signing secret, and timeout",
      async () => {
        const requestedArns:
          string[] = [];

        const result =
          await loadWebhookRuntimeConfig({
            environment:
              environment(),

            getSecretString:
              async (
                secretArn,
              ) => {
                requestedArns.push(
                  secretArn,
                );

                return secretPayload();
              },
          });

        expect(
          requestedArns,
        ).toHaveLength(
          1,
        );

        expect(
          result,
        ).toEqual({
          targetUrl:
            "https://example.com/hooks/incidents",

          signingSecret:
            SIGNING_SECRET,

          timeoutMs:
            5000,
        });
      },
    );

    it(
      "rejects a missing secret ARN",
      async () => {
        await expect(
          loadWebhookRuntimeConfig({
            environment:
              environment({
                WEBHOOK_CONFIG_SECRET_ARN:
                  "",
              }),

            getSecretString:
              async () =>
                secretPayload(),
          }),
        ).rejects.toBeInstanceOf(
          WebhookNotifierConfigurationError,
        );
      },
    );

    it(
      "rejects malformed secret JSON",
      async () => {
        await expect(
          loadWebhookRuntimeConfig({
            environment:
              environment(),

            getSecretString:
              async () =>
                "{not-json",
          }),
        ).rejects.toThrow(
          "must contain valid JSON",
        );
      },
    );

    it(
      "rejects non-HTTPS targets",
      async () => {
        await expect(
          loadWebhookRuntimeConfig({
            environment:
              environment(),

            getSecretString:
              async () =>
                secretPayload({
                  target_url:
                    "http://example.com/hooks/incidents",
                }),
          }),
        ).rejects.toThrow(
          "must use HTTPS",
        );
      },
    );

    it(
      "rejects short signing secrets",
      async () => {
        await expect(
          loadWebhookRuntimeConfig({
            environment:
              environment(),

            getSecretString:
              async () =>
                secretPayload({
                  signing_secret:
                    "too-short",
                }),
          }),
        ).rejects.toThrow(
          "at least 32 UTF-8 bytes",
        );
      },
    );

    it.each([
      "0",
      "-1",
      "30001",
      "1.5",
      "not-a-number",
    ])(
      "rejects invalid timeout %s",
      async (
        timeoutValue,
      ) => {
        await expect(
          loadWebhookRuntimeConfig({
            environment:
              environment({
                WEBHOOK_HTTP_TIMEOUT_MS:
                  timeoutValue,
              }),

            getSecretString:
              async () =>
                secretPayload(),
          }),
        ).rejects.toBeInstanceOf(
          WebhookNotifierConfigurationError,
        );
      },
    );
  },
);
