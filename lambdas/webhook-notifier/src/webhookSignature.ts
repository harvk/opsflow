import { createHmac, timingSafeEqual } from "node:crypto";

const SIGNATURE_VERSION = "v1";

const SHA256_HEX_LENGTH = 64;

const MINIMUM_SECRET_BYTES = 32;

export interface WebhookSignatureInput {
  body: string;

  timestampSeconds: number;

  secret: string;
}

export interface WebhookSignatureVerificationInput extends WebhookSignatureInput {
  signatureHeader: string;

  currentTimestampSeconds: number;

  toleranceSeconds: number;
}

export class InvalidWebhookSigningSecretError extends Error {
  constructor(message: string) {
    super(message);

    this.name = "InvalidWebhookSigningSecretError";
  }
}

export class InvalidWebhookTimestampError extends Error {
  constructor(message: string) {
    super(message);

    this.name = "InvalidWebhookTimestampError";
  }
}

function validateSecret(secret: string): void {
  const bytes = Buffer.byteLength(secret, "utf8");

  if (bytes < MINIMUM_SECRET_BYTES) {
    throw new InvalidWebhookSigningSecretError(
      "Webhook signing secret must " +
        `contain at least ${MINIMUM_SECRET_BYTES} ` +
        "UTF-8 bytes.",
    );
  }
}

function validateTimestamp(timestampSeconds: number): void {
  if (!Number.isSafeInteger(timestampSeconds) || timestampSeconds <= 0) {
    throw new InvalidWebhookTimestampError(
      "Webhook timestamp must be a " +
        "positive safe integer expressed " +
        "as Unix seconds.",
    );
  }
}

function buildSignaturePayload(
  timestampSeconds: number,

  body: string,
): string {
  return `${timestampSeconds}.${body}`;
}

function calculateDigest(input: WebhookSignatureInput): string {
  validateSecret(input.secret);

  validateTimestamp(input.timestampSeconds);

  const payload = buildSignaturePayload(input.timestampSeconds, input.body);

  return createHmac("sha256", input.secret)
    .update(payload, "utf8")
    .digest("hex");
}

function parseSignatureHeader(value: string): string | null {
  const prefix = `${SIGNATURE_VERSION}=`;

  if (!value.startsWith(prefix)) {
    return null;
  }

  const digest = value.slice(prefix.length);

  if (digest.length !== SHA256_HEX_LENGTH) {
    return null;
  }

  if (!/^[0-9a-f]+$/u.test(digest)) {
    return null;
  }

  return digest;
}

export function createWebhookSignature(input: WebhookSignatureInput): string {
  const digest = calculateDigest(input);

  return `${SIGNATURE_VERSION}=${digest}`;
}

export function verifyWebhookSignature(
  input: WebhookSignatureVerificationInput,
): boolean {
  validateSecret(input.secret);

  validateTimestamp(input.timestampSeconds);

  validateTimestamp(input.currentTimestampSeconds);

  if (
    !Number.isSafeInteger(input.toleranceSeconds) ||
    input.toleranceSeconds < 0
  ) {
    throw new InvalidWebhookTimestampError(
      "Webhook signature tolerance must " + "be a non-negative safe integer.",
    );
  }

  const ageSeconds = Math.abs(
    input.currentTimestampSeconds - input.timestampSeconds,
  );

  if (ageSeconds > input.toleranceSeconds) {
    return false;
  }

  const actualDigest = parseSignatureHeader(input.signatureHeader);

  if (actualDigest === null) {
    return false;
  }

  const expectedDigest = calculateDigest({
    body: input.body,

    timestampSeconds: input.timestampSeconds,

    secret: input.secret,
  });

  const actual = Buffer.from(actualDigest, "hex");

  const expected = Buffer.from(expectedDigest, "hex");

  if (actual.length !== expected.length) {
    return false;
  }

  return timingSafeEqual(actual, expected);
}
