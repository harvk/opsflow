# OpsFlow Webhook Notifier

The OpsFlow webhook notifier is a secondary delivery adapter for versioned
OpsFlow notifications.

It currently consumes:

- notification type: `incident.updated`
- schema version: `1.0`

The authoritative notification schema is:

`contracts/notifications/incident-updated-v1.schema.json`

## Authentication

Webhook requests are authenticated with HMAC-SHA256.

Each request contains:

- `X-OpsFlow-Webhook-Timestamp`
- `X-OpsFlow-Webhook-Signature`

The signature header uses:

`v1=<lowercase hexadecimal SHA-256 digest>`

## Canonical signature payload

The signature is calculated from the exact request body.

The canonical signing payload is:

`<timestamp>.<raw-body>`

where:

- `timestamp` is the exact decimal Unix timestamp value sent in
  `X-OpsFlow-Webhook-Timestamp`;
- `.` is one ASCII period character;
- `raw-body` is the exact HTTP request body before any receiver-side JSON
  parsing or reserialization.

The sender computes:

`HMAC-SHA256(secret, "<timestamp>.<raw-body>")`

and encodes the digest as lowercase hexadecimal.

## Receiver verification

A webhook receiver should:

1. read the raw request body;
2. read `X-OpsFlow-Webhook-Timestamp`;
3. read `X-OpsFlow-Webhook-Signature`;
4. reject unsupported signature versions;
5. reject timestamps outside its accepted replay window;
6. calculate HMAC-SHA256 using the shared webhook secret;
7. compare signatures using a constant-time comparison;
8. parse and process the JSON only after signature verification succeeds.

Receivers must not parse the JSON and then reconstruct a new JSON string for
signature verification. JSON whitespace and serialization are part of the
signed byte sequence.

## Replay protection

The timestamp participates in the HMAC signature.

The recommended maximum request age is 300 seconds.

A request whose timestamp differs from the receiver's current time by more
than the accepted tolerance should be rejected even when its HMAC signature
is otherwise valid.

Receivers that require stronger replay protection can additionally persist
successfully processed `event_id` values for an application-specific
deduplication window.

## Event identity

`X-OpsFlow-Event-Id` contains the same durable `event_id` carried in the
notification body.

Webhook delivery is at least once. A successful webhook can be delivered
again if the source SQS message is retried.

Consumers should use `event_id` as the logical notification identity when
duplicate processing would otherwise create an incorrect side effect.

## Transport security

Webhook target URLs must use HTTPS.

OpsFlow rejects webhook URLs containing embedded username/password
credentials.

The shared signing secret is not placed in the URL, notification body, or
ordinary identity headers.

Secret retrieval and AWS Secrets Manager integration are implemented in a
later deployment stage.
