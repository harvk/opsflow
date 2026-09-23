# OpsFlow Webhook Notifier

The OpsFlow webhook notifier is a secondary delivery adapter for versioned
OpsFlow notifications.

It currently consumes:

- notification type: `incident.updated`
- schema version: `1.0`

The authoritative notification schema is:

`contracts/notifications/incident-updated-v1.schema.json`

## Delivery architecture

The webhook adapter is designed to consume a dedicated Amazon SQS queue.

It does not compete with the WebSocket notifier for records from the same
queue.

The dedicated queue is introduced in a later infrastructure phase.

Each SQS record contains one complete `incident.updated` notification.

Before any HTTP side effect occurs, the worker:

1. parses the SQS message body;
2. validates it against the shared notification contract;
3. creates the exact HTTP request body;
4. generates a fresh delivery timestamp;
5. creates an HMAC-SHA256 signature;
6. performs a bounded HTTPS POST request.

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

A new signature timestamp is generated for every webhook delivery attempt.

When SQS retries the same logical event:

- the notification body remains unchanged;
- `event_id` remains unchanged;
- the timestamp is refreshed;
- the HMAC signature is refreshed.

This permits legitimate retries to remain inside the receiver's replay
window while preserving the same logical event identity.

Receivers that require stronger replay protection can additionally persist
successfully processed `event_id` values for an application-specific
deduplication window.

## Event identity

`X-OpsFlow-Event-Id` contains the same durable `event_id` carried in the
notification body.

Webhook delivery is at least once. A successful webhook can be delivered
again if an SQS record is retried.

Consumers should use `event_id` as the logical notification identity when
duplicate processing would otherwise create an incorrect side effect.

## HTTP transport

Webhook delivery uses HTTPS POST.

The HTTP client applies a mandatory bounded timeout.

The maximum accepted configured timeout is 30 seconds.

Automatic redirects are disabled. A redirect response is treated as an HTTP
delivery failure rather than automatically forwarding the signed request to
another destination.

This prevents the HMAC signature and notification body from being
automatically forwarded to a redirect-selected host.

## HTTP response classification

All HTTP 2xx responses are successful deliveries.

The following HTTP responses are classified as retryable:

- 408 Request Timeout
- 425 Too Early
- 429 Too Many Requests
- all 5xx responses

Other non-2xx responses are classified as non-retryable HTTP failures.

Network errors and local request timeouts are classified as retryable.

Classification describes the expected nature of the failure. The SQS worker
still returns both retryable and non-retryable failed webhook records through
partial batch failure handling.

This prevents permanent failures from being silently discarded. The
dedicated webhook SQS redrive policy will eventually move repeatedly failing
records into the webhook DLQ for investigation.

## SQS partial-batch semantics

Every SQS record is processed independently.

A failure for one webhook delivery does not prevent later records in the
same Lambda batch from being attempted.

The worker returns only failed SQS message identifiers in
`batchItemFailures`.

This provides at-least-once webhook delivery while isolating failures between
records.

Malformed JSON and notification-contract failures are also returned as
failed records and are never delivered over HTTP.

## Transport security

Webhook target URLs must use HTTPS.

OpsFlow rejects webhook URLs containing embedded username/password
credentials.

The shared signing secret is not placed in the URL, notification body, or
ordinary identity headers.

Secret retrieval and AWS Secrets Manager integration are implemented in a
later deployment stage.
