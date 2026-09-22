# OpsFlow Realtime Notification Contracts

This directory defines the public notification contracts emitted by
OpsFlow realtime notification infrastructure.

## Current contract

The current realtime notification contract is:

- `incident-updated-v1.schema.json`
- notification type: `incident.updated`
- schema version: `1.0`

The canonical example is located at:

- `examples/valid-incident-updated-v1.json`

## Source event

`incident.updated` is currently produced from the durable internal event:

`incident.task.completed`

The realtime notifier preserves the durable event identity and correlation
fields when translating the internal event into the public notification.

## Delivery guarantee

Realtime WebSocket notification delivery is **at least once**.

Amazon SQS may redeliver a notification source message whenever a delivery
attempt is reported as failed. As a result, a WebSocket consumer can receive
the same logical notification more than once.

OpsFlow does not claim exactly-once WebSocket delivery.

## Event identity

`event_id` identifies the logical notification event.

The same logical event retains the same `event_id` when its source SQS
message is retried.

Consumers should use `event_id` as their deduplication identity when
duplicate processing would otherwise create an incorrect user-visible side
effect.

## Fan-out failure isolation

For one notification, the realtime notifier attempts every discovered
WebSocket connection.

A transient delivery failure for one connection does not prevent delivery
attempts to the remaining connections.

After all connections have been attempted, transient failures are aggregated
into one notifier failure. The SQS handler reports that source record through
partial batch failure semantics so the record can be retried independently
of successful records from the same SQS batch.

## Duplicate delivery after partial fan-out

A successful WebSocket delivery cannot be atomically committed together with
all other WebSocket deliveries in the fan-out.

For example:

1. connection A receives the event successfully;
2. connection B encounters a transient delivery failure;
3. the notifier finishes attempting the remaining connections;
4. the source SQS record is reported as failed;
5. SQS retries the source record;
6. connection A can receive the same `event_id` again.

This behavior is expected under the at-least-once delivery contract.

## Stale connections

API Gateway `GoneException` indicates that the target WebSocket connection is
no longer active.

A gone connection is not treated as a transient notification failure.

The notifier attempts to remove the stale connection record and continues
fan-out to the remaining connections.

Deletion of an already-stale connection record is best effort. A cleanup
failure is logged but does not cause the source notification to retry,
because retrying the complete event solely for stale-record cleanup would
unnecessarily duplicate delivery to healthy clients.

## Ordering

The realtime notification contract does not guarantee global ordering across
different incidents, events, SQS records, Lambda invocations, or WebSocket
clients.

Consumers should use the event fields and application state rather than
assuming that arrival order alone determines the final Incident state.

## Contract validation

The realtime notifier validates:

1. the inbound `incident.task.completed` event; and
2. the outbound `incident.updated` message.

An outbound message that fails the versioned notification schema is rejected
before connection discovery or WebSocket delivery begins.

## Future consumers

Frontend WebSocket clients and future notification adapters should consume
the versioned contract rather than recreating notification shapes
independently.

Consumers that need duplicate suppression should deduplicate by `event_id`.

## Channel isolation

Realtime notification delivery is scoped to the server-configured WebSocket
channel.

The WebSocket connection store persists every connection under a channel
partition. The notifier queries only the configured channel partition rather
than scanning all stored connections.

The delivery layer also verifies the `channel` field of every returned
connection before attempting delivery.

A connection whose stored channel does not match the notifier target channel
is skipped and produces a structured warning log.

This second validation is intentional defense in depth. It prevents a
malformed repository result, corrupted record, test double, or future storage
regression from causing cross-channel notification delivery.

Clients do not currently choose arbitrary notification channels during the
WebSocket handshake. Channel assignment remains server controlled through
the notifier's deployment configuration.
