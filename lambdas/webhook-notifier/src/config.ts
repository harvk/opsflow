import {
  GetSecretValueCommand,
  SecretsManagerClient,
} from "@aws-sdk/client-secrets-manager";

const WEBHOOK_CONFIG_SECRET_ARN_ENV =
  "WEBHOOK_CONFIG_SECRET_ARN";

const WEBHOOK_HTTP_TIMEOUT_MS_ENV =
  "WEBHOOK_HTTP_TIMEOUT_MS";

const MAXIMUM_HTTP_TIMEOUT_MS =
  30_000;

const MINIMUM_SIGNING_SECRET_BYTES =
  32;

const secretsManagerClient =
  new SecretsManagerClient({});

export interface WebhookRuntimeConfig {
  targetUrl: string;

  signingSecret: string;

  timeoutMs: number;
}

export interface WebhookRuntimeConfigDependencies {
  environment?: NodeJS.ProcessEnv;

  getSecretString?: (
    secretArn: string,
  ) => Promise<string>;
}

export class WebhookNotifierConfigurationError
  extends Error {
  constructor(message: string) {
    super(message);

    this.name =
      "WebhookNotifierConfigurationError";
  }
}

function requireEnvironmentVariable(
  environment: NodeJS.ProcessEnv,
  name: string,
): string {
  const value =
    environment[name]?.trim();

  if (!value) {
    throw new WebhookNotifierConfigurationError(
      `${name} must be configured.`,
    );
  }

  return value;
}

function parseHttpTimeout(
  environment: NodeJS.ProcessEnv,
): number {
  const rawValue =
    requireEnvironmentVariable(
      environment,
      WEBHOOK_HTTP_TIMEOUT_MS_ENV,
    );

  const value =
    Number(rawValue);

  if (
    !Number.isSafeInteger(value)
    || value <= 0
    || value > MAXIMUM_HTTP_TIMEOUT_MS
  ) {
    throw new WebhookNotifierConfigurationError(
      `${WEBHOOK_HTTP_TIMEOUT_MS_ENV} must be a positive `
      + `integer no greater than ${MAXIMUM_HTTP_TIMEOUT_MS}.`,
    );
  }

  return value;
}

function requireSecretField(
  value: unknown,
  field: string,
): string {
  if (
    typeof value !== "string"
    || value.trim().length === 0
  ) {
    throw new WebhookNotifierConfigurationError(
      `Webhook notifier secret field ${field} must be a non-empty string.`,
    );
  }

  return value.trim();
}

function validateTargetUrl(
  value: string,
): string {
  let parsed: URL;

  try {
    parsed =
      new URL(value);
  } catch {
    throw new WebhookNotifierConfigurationError(
      "Webhook notifier target_url must be a valid absolute URL.",
    );
  }

  if (parsed.protocol !== "https:") {
    throw new WebhookNotifierConfigurationError(
      "Webhook notifier target_url must use HTTPS.",
    );
  }

  if (
    parsed.username.length > 0
    || parsed.password.length > 0
  ) {
    throw new WebhookNotifierConfigurationError(
      "Webhook notifier target_url must not contain embedded credentials.",
    );
  }

  return parsed.toString();
}

function parseSecretPayload(
  rawSecret: string,
): {
  targetUrl: string;

  signingSecret: string;
} {
  let parsed: unknown;

  try {
    parsed =
      JSON.parse(rawSecret) as unknown;
  } catch {
    throw new WebhookNotifierConfigurationError(
      "Webhook notifier secret must contain valid JSON.",
    );
  }

  if (
    typeof parsed !== "object"
    || parsed === null
    || Array.isArray(parsed)
  ) {
    throw new WebhookNotifierConfigurationError(
      "Webhook notifier secret must contain a JSON object.",
    );
  }

  const secretObject =
    parsed as Record<string, unknown>;

  const targetUrl =
    validateTargetUrl(
      requireSecretField(
        secretObject.target_url,
        "target_url",
      ),
    );

  const signingSecret =
    requireSecretField(
      secretObject.signing_secret,
      "signing_secret",
    );

  if (
    Buffer.byteLength(
      signingSecret,
      "utf8",
    )
    < MINIMUM_SIGNING_SECRET_BYTES
  ) {
    throw new WebhookNotifierConfigurationError(
      "Webhook notifier signing_secret must contain "
      + `at least ${MINIMUM_SIGNING_SECRET_BYTES} UTF-8 bytes.`,
    );
  }

  return {
    targetUrl,
    signingSecret,
  };
}

async function getSecretString(
  secretArn: string,
): Promise<string> {
  const response =
    await secretsManagerClient.send(
      new GetSecretValueCommand({
        SecretId:
          secretArn,
      }),
    );

  const secretString =
    response.SecretString;

  if (
    typeof secretString !== "string"
    || secretString.length === 0
  ) {
    throw new WebhookNotifierConfigurationError(
      "Webhook notifier secret must be stored as SecretString JSON.",
    );
  }

  return secretString;
}

export async function loadWebhookRuntimeConfig(
  dependencies:
    WebhookRuntimeConfigDependencies = {},
): Promise<WebhookRuntimeConfig> {
  const environment =
    dependencies.environment
    ?? process.env;

  const secretArn =
    requireEnvironmentVariable(
      environment,
      WEBHOOK_CONFIG_SECRET_ARN_ENV,
    );

  const timeoutMs =
    parseHttpTimeout(
      environment,
    );

  const secretReader =
    dependencies.getSecretString
    ?? getSecretString;

  const rawSecret =
    await secretReader(
      secretArn,
    );

  const secretConfig =
    parseSecretPayload(
      rawSecret,
    );

  return {
    targetUrl:
      secretConfig.targetUrl,

    signingSecret:
      secretConfig.signingSecret,

    timeoutMs,
  };
}
